#!/usr/bin/env python3

import argparse
import atexit
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from openai import OpenAI
from tqdm import tqdm


SYSTEM_PROMPT = """/no_think
Compare a candidate chess explanation with a reference.
Score correctness, instruction_following, helpfulness, faithfulness, and fluency
from 0 to 10. Set overall to their mean. Return only compact JSON with exactly
those six numeric keys plus "reason". Keep reason under 5 words."""

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
    """Derive overall from component scores instead of trusting model output."""
    component_scores = [scores.get(column) for column in COMPONENT_SCORE_COLUMNS]
    if not all(
        isinstance(score, (int, float)) and not isinstance(score, bool)
        for score in component_scores
    ):
        return None
    return round(sum(component_scores) / len(component_scores), 2)


def judge(client, prediction, reference, model):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=96,
        response_format={"type": "json_object"},
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

    text = response.choices[0].message.content

    try:
        scores = json.loads(text)
        if not isinstance(scores, dict):
            raise TypeError("judge response is not a JSON object")
        scores["overall"] = calculate_overall(scores)
        return scores
    except (json.JSONDecodeError, TypeError):
        return {
            "correctness": None,
            "instruction_following": None,
            "helpfulness": None,
            "faithfulness": None,
            "fluency": None,
            "overall": None,
            "reason": text,
        }


def read_tsv(path,separator="\t"):
    dataframe = pd.read_csv(path, sep=separator, dtype=str, keep_default_na=False)
    actual_columns = list(dataframe.columns)

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            f"{path} has the wrong columns or column order.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    duplicate_keys = dataframe.duplicated(MATCH_COLUMNS, keep=False)
    if duplicate_keys.any():
        duplicates = dataframe.loc[duplicate_keys, MATCH_COLUMNS].to_dict("records")
        raise ValueError(
            f"{path} contains duplicate (type, row_id) keys: {duplicates}"
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
    candidate_indexed = candidate.set_index(MATCH_COLUMNS, drop=False)
    reference_indexed = reference.set_index(MATCH_COLUMNS, drop=False)

    candidate_keys = set(candidate_indexed.index)
    reference_keys = set(reference_indexed.index)
    missing_keys = sorted(reference_keys - candidate_keys)
    extra_keys = sorted(candidate_keys - reference_keys)

    if missing_keys or extra_keys:
        raise ValueError(
            "candidate and reference rows do not match. "
            f"Missing keys: {missing_keys}; extra keys: {extra_keys}"
        )

    candidate_aligned = candidate_indexed.loc[reference_indexed.index]
    metadata_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in {"analyse", "analyser"}
    ]
    mismatches = []

    for key in reference_indexed.index:
        for column in metadata_columns:
            candidate_value = candidate_aligned.at[key, column]
            reference_value = reference_indexed.at[key, column]
            if candidate_value != reference_value:
                row_type, row_id = key
                mismatches.append(
                    {
                        "type": row_type,
                        "row_id": row_id,
                        "column": column,
                        "candidate": candidate_value,
                        "reference": reference_value,
                    }
                )

    if mismatches:
        preview = json.dumps(mismatches[:10], ensure_ascii=False, indent=2)
        raise ValueError(
            f"candidate differs from the reference in {len(mismatches)} "
            f"non-output cells. First differences:\n{preview}"
        )

    return candidate_aligned, reference_indexed


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
            "Compare a generated TSV against evaluation_dataset.tsv and judge each "
            "generated analysis with a local OpenAI-compatible model."
        )
    )
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "processed" / "chess_coach_dataset_complete.csv"), help="generated/candidate TSV")
    parser.add_argument(
        "--reference",
        default=str(Path(__file__).with_name("evaluation_dataset.tsv")),
        help="reference TSV (default: evaluation/evaluation_dataset.tsv)",
    )
    parser.add_argument("--output", default="judged.json")
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
        candidate = read_tsv(args.input,separator=',')
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

    report = {
        "candidate_file": str(Path(args.input).resolve()),
        "reference_file": str(Path(args.reference).resolve()),
        "model": args.model,
        "matched_rows": len(results),
        "columns_match_exactly": True,
        "metadata_matches_exactly": True,
        "overall_statistics": score_statistics(results),
        "category_statistics": category_statistics(results),
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(report, output_file, ensure_ascii=False, indent=2)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
