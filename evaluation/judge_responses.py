#!/usr/bin/env python3

import argparse
import atexit
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from openai import OpenAI
from tqdm import tqdm

from app.artifact_naming import evaluation_filename, model_name_from_dataset


SYSTEM_PROMPT = r"""/no_think
REFERENCE is the only ground truth. Compare its central chess claims with
CANDIDATE. Accept paraphrases and omitted minor details. Do not infer a board
position. Unsupported details are uncertain; strong added claims (checkmate,
winning material, forced tactics) reduce correctness and faithfulness.

Score independently from 0-10:
- correctness: agreement with reference facts
- instruction_following: relevant learner-facing chess explanation; factual
  disagreement alone does not lower this metric
- helpfulness: clearly conveys the reference's lesson, cause, or consequence
- faithfulness: stays grounded in the reference; penalize unsupported additions
- fluency: grammar and clarity only; factual errors do not lower this metric

Use partial credit: 10=fully aligned, 8-9=minor issue, 6-7=mostly aligned,
4-5=mixed overlap, 2-3=major disagreement with slight overlap, 0-1=wholly
contradictory, irrelevant, or unusable. Do not automatically give every metric
the same score.

Return exactly one JSON object on one line, using this exact shape:
{"correctness":0,"instruction_following":0,"helpfulness":0,"faithfulness":0,"fluency":0,"reason":"short quoted reason"}

Requirements:
- Replace each 0 with the chosen integer score.
- Keep reason quoted and at most five words.
- Do not return overall; the application calculates it.
- Return no Markdown or text outside the JSON.
"""

EXPECTED_COLUMNS = [
    "row_id",
    "before_fen",
    "after_fen",
    "move",
    "prompt",
    "analyse",
    "analyser",
    "move type",
    "move evaluation",
    "type",
]

MATCH_COLUMNS = ["type", "row_id"]
SCORE_COLUMNS = [
    "correctness",
    "instruction_following",
    "helpfulness",
    "faithfulness",
    "fluency",
    "overall",
]
COMPONENT_SCORE_COLUMNS = SCORE_COLUMNS[:-1]

JUDGE_RESPONSE_SCHEMA = {
    "name": "chess_evaluation_scores",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            column: {"type": "integer", "minimum": 0, "maximum": 10}
            for column in COMPONENT_SCORE_COLUMNS
        }
        | {"reason": {"type": "string"}},
        "required": COMPONENT_SCORE_COLUMNS + ["reason"],
        "additionalProperties": False,
    },
}


class LlamaServer:
    def __init__(
        self,
        server_path,
        model_path,
        port=8080,
        threads=12,
        parallel=4,
        context_size=2048,
    ):
        self.server_path = server_path
        self.model_path = model_path
        self.port = port
        self.threads = threads
        self.parallel = parallel
        self.context_size = context_size
        self.process = None

    def start(self):
        print("Starting llama-server...")

        self.process = subprocess.Popen(
            [
                self.server_path,
                "--model",
                self.model_path,
                "--port",
                str(self.port),
                "--threads",
                str(self.threads),
                "--threads-batch",
                str(self.threads),
                "--parallel",
                str(self.parallel),
                "--ctx-size",
                str(self.context_size),
                "--jinja",
                "--reasoning",
                "off",
                "--reasoning-budget",
                "0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

        self.wait_until_ready()
        print("llama-server is ready.")

    def wait_until_ready(self, timeout=120):
        start = time.time()

        while True:
            if self.process.poll() is not None:
                raise RuntimeError("llama-server exited unexpectedly.")

            try:
                response = requests.get(
                    f"http://localhost:{self.port}/health",
                    timeout=1,
                )

                if response.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass

            if time.time() - start > timeout:
                raise TimeoutError("Timed out waiting for llama-server.")

            time.sleep(1)

    def stop(self):
        if self.process is None:
            return

        print("Stopping llama-server...")
        self.process.terminate()

        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        self.process = None
        print("Done.")


def build_prompt(prediction, reference):
    return f"Candidate:\n{prediction}\n\nReference:\n{reference}"


def calculate_overall(scores):
    """Calculate the weighted overall score from validated component scores."""
    component_scores = {
        column: scores.get(column) for column in COMPONENT_SCORE_COLUMNS
    }
    if not all(
        isinstance(score, (int, float)) and not isinstance(score, bool)
        for score in component_scores.values()
    ):
        return None
    return round(
        0.35 * component_scores["correctness"]
        + 0.25 * component_scores["faithfulness"]
        + 0.20 * component_scores["helpfulness"]
        + 0.10 * component_scores["instruction_following"]
        + 0.10 * component_scores["fluency"],
        2,
    )


def parse_judge_response(text):
    """Parse and validate one judge response before calculating overall."""
    scores = json.loads(text)
    if not isinstance(scores, dict):
        raise ValueError("judge response is not a JSON object")

    expected_keys = set(COMPONENT_SCORE_COLUMNS) | {"reason"}
    if set(scores) != expected_keys:
        raise ValueError(
            f"judge response keys must be {sorted(expected_keys)}, got {sorted(scores)}"
        )

    for column in COMPONENT_SCORE_COLUMNS:
        score = scores[column]
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 10:
            raise ValueError(f"{column} must be an integer from 0 to 10")
    if not isinstance(scores["reason"], str):
        raise ValueError("reason must be a string")

    scores["overall"] = calculate_overall(scores)
    return scores


def recover_scores_from_malformed_response(text):
    """Recover the five integer scores when only the reason JSON is malformed."""
    scores = {}
    for column in COMPONENT_SCORE_COLUMNS:
        match = re.search(rf'"{re.escape(column)}"\s*:\s*(-?\d+)', text)
        if match is None:
            return None
        score = int(match.group(1))
        if not 0 <= score <= 10:
            return None
        scores[column] = score

    scores.update(
        {
            "overall": calculate_overall(scores),
            "reason": "Recovered malformed response",
            "parse_error": "model returned malformed JSON",
            "raw_response": text,
        }
    )
    return scores


def judge(client, prediction, reference, model, max_attempts=3):
    last_text = ""
    last_error = "judge returned no response"

    for _ in range(max_attempts):
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=192,
            response_format={
                "type": "json_schema",
                "json_schema": JUDGE_RESPONSE_SCHEMA,
            },
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_prompt(prediction, reference),
                },
            ],
        )

        last_text = response.choices[0].message.content or ""
        try:
            return parse_judge_response(last_text)
        except (json.JSONDecodeError, ValueError) as error:
            last_error = str(error)

    recovered_scores = recover_scores_from_malformed_response(last_text)
    if recovered_scores is not None:
        return recovered_scores

    return {
        "correctness": None,
        "instruction_following": None,
        "helpfulness": None,
        "faithfulness": None,
        "fluency": None,
        "overall": None,
        "reason": "Invalid judge response",
        "parse_error": last_error,
        "raw_response": last_text,
    }


def read_tsv(path, separator="\t"):
    dataframe = pd.read_csv(path, sep=separator, dtype=str, keep_default_na=False)

    missing_columns = [
        column for column in EXPECTED_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            f"{path} is missing required columns: {missing_columns}. "
            f"Available columns: {list(dataframe.columns)}"
        )

    return dataframe


def resolve_model_path(requested_path):
    if requested_path:
        path = Path(requested_path).expanduser()
        if not path.is_file():
            raise ValueError(f"GGUF model does not exist or is incomplete: {path}")
        return path

    models_directory = Path("/home/seyed/models")
    matches = sorted(
        path
        for path in models_directory.rglob("*.gguf")
        if "qwen3.5" in path.name.lower()
        and "q4_k_m" in path.name.lower().replace("-", "_")
        and path.is_file()
    )
    if not matches:
        raise ValueError(
            "No completed Qwen3.5 Q4_K_M GGUF was found under "
            f"{models_directory}. Finish the download or pass --gguf PATH."
        )

    if len(matches) > 1:
        print(f"Found multiple Qwen3.5 models; using {matches[0]}")
    return matches[0]


def align_and_compare(candidate, reference):
    """Index candidate and reference rows without validating their contents."""
    candidate_indexed = candidate.set_index(MATCH_COLUMNS, drop=False)
    reference_indexed = reference.set_index(MATCH_COLUMNS, drop=False)
    return candidate_indexed, reference_indexed


def score_statistics(results):
    statistics = {}
    for column in SCORE_COLUMNS:
        values = [
            result["scores"].get(column)
            for result in results
            if isinstance(result["scores"].get(column), (int, float))
        ]
        if not values:
            statistics[column] = {
                "count": 0,
                "mean": None,
                "median": None,
                "q1": None,
                "q3": None,
                "iqr": None,
                "min": None,
                "max": None,
            }
            continue

        series = pd.Series(values, dtype=float)
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        statistics[column] = {
            "count": len(values),
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(q3 - q1, 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
        }
    return statistics


def category_statistics(results):
    categories = sorted({result["type"] for result in results})
    return {
        category: score_statistics(
            [result for result in results if result["type"] == category]
        )
        for category in categories
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare a generated CSV against evaluation_dataset.tsv and judge each "
            "generated analysis with a local OpenAI-compatible model."
        )
    )
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--input",
        required=True,
        help=(
            "candidate CSV named like "
            "chess_coach_dataset_complete__model_gemini-3.5-flash.csv"
        ),
    )
    parser.add_argument(
        "--reference",
        default=str(Path(__file__).with_name("evaluation_dataset.tsv")),
        help="reference TSV (default: evaluation/evaluation_dataset.tsv)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="output JSON path (default: evaluation/judged__model_<answer-model>.json)",
    )
    parser.add_argument(
        "--server",
        default="/home/seyed/models/llama-b9536/llama-server",
    )
    parser.add_argument(
        "--gguf",
        default=None,
        help=(
            "Qwen3.5 Q4_K_M file; if omitted, search /home/seyed/models "
            "automatically"
        ),
    )
    parser.add_argument("--model", default="qwen3.5")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    try:
        answer_model = model_name_from_dataset(args.input)
        candidate = read_tsv(args.input, separator=',')
        reference = read_tsv(args.reference)
        candidate, reference = align_and_compare(candidate, reference)
        model_path = resolve_model_path(args.gguf)
    except (OSError, pd.errors.ParserError, ValueError) as error:
        parser.error(str(error))

    server = LlamaServer(
        server_path=args.server,
        model_path=model_path,
        port=args.port,
        threads=args.threads,
        parallel=args.workers,
    )
    atexit.register(server.stop)
    server.start()

    client = OpenAI(
        base_url=f"http://localhost:{args.port}/v1",
        api_key="not-needed",
    )

    def evaluate_row(position, key):
        candidate_row = candidate.loc[key]
        reference_row = reference.loc[key]
        scores = judge(
            client,
            prediction=candidate_row["analyse"],
            reference=reference_row["analyse"],
            model=args.model,
        )
        return position, (
            {
                "type": reference_row["type"],
                "row_id": reference_row["row_id"],
                "move": reference_row["move"],
                "candidate_analyser": candidate_row["analyser"],
                "candidate": candidate_row["analyse"],
                "reference": reference_row["analyse"],
                "scores": scores,
            }
        )

    ordered_results = [None] * len(reference)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(evaluate_row, position, key)
            for position, key in enumerate(reference.index)
        ]
        for future in tqdm(as_completed(futures), total=len(futures)):
            position, result = future.result()
            ordered_results[position] = result

    results = ordered_results

    output_path = Path(args.output) if args.output else (
        PROJECT_ROOT / "evaluation" / evaluation_filename(answer_model)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "candidate_file": str(Path(args.input).resolve()),
        "reference_file": str(Path(args.reference).resolve()),
        "answer_model": answer_model,
        "judge_model": args.model,
        "matched_rows": len(results),
        "required_columns_present": True,
        "overall_statistics": score_statistics(results),
        "category_statistics": category_statistics(results),
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(report, output_file, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
