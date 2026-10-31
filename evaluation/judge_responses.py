#!/usr/bin/env python3

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

from app.artifact_naming import evaluation_filename, model_name_from_dataset
from scripts.llama_server import LlamaServer, LlamaServerConfig, default_cpu_threads


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

REFERENCE_COLUMNS = ["row_id", "move", "analyse", "type"]
CANDIDATE_COLUMNS = ["row_id", "analyse", "analyser", "type"]
# Kept as the public name used by existing callers. These are the only columns
# both inputs need in order to align and score rows.
EXPECTED_COLUMNS = CANDIDATE_COLUMNS

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
            max_tokens=128,
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


def read_tsv(path, separator="\t", required_columns=None):
    dataframe = pd.read_csv(path, sep=separator, dtype=str, keep_default_na=False)
    required_columns = required_columns or EXPECTED_COLUMNS

    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
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
        if "gemma-4" in path.name.lower()
        and path.is_file()
    )
    if not matches:
        raise ValueError(
            "No Gemma 4 GGUF was found under "
            f"{models_directory}. Pass --gguf PATH."
        )

    if len(matches) > 1:
        print(f"Found multiple matching models; using {matches[0]}")
    return matches[0]


def align_and_compare(candidate, reference):
    """Index and validate one-to-one candidate/reference row alignment."""
    candidate_indexed = candidate.set_index(MATCH_COLUMNS, drop=False)
    reference_indexed = reference.set_index(MATCH_COLUMNS, drop=False)

    for name, dataframe in (
        ("candidate", candidate_indexed),
        ("reference", reference_indexed),
    ):
        duplicate_keys = dataframe.index[dataframe.index.duplicated()].unique().tolist()
        if duplicate_keys:
            raise ValueError(
                f"{name} contains duplicate {MATCH_COLUMNS} keys: "
                f"{duplicate_keys[:5]}"
            )

    missing_keys = reference_indexed.index.difference(candidate_indexed.index).tolist()
    extra_keys = candidate_indexed.index.difference(reference_indexed.index).tolist()
    if missing_keys or extra_keys:
        details = []
        if missing_keys:
            details.append(f"missing candidate keys: {missing_keys[:5]}")
        if extra_keys:
            details.append(f"unexpected candidate keys: {extra_keys[:5]}")
        raise ValueError("candidate/reference rows do not align; " + "; ".join(details))

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
    load_dotenv()
    parser = argparse.ArgumentParser(
        description=(
            "Compare a generated CSV against evaluation_dataset.tsv and judge each "
            "generated analysis with a local llama-server judge model."
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
        "--cpu-server",
        default=os.getenv("LLAMA_CPU_SERVER", "llama-server"),
        help="CPU llama-server executable",
    )
    parser.add_argument(
        "--gguf",
        default=os.getenv("JUDGE_LLM_PATH", "/home/seyed/models/gemma-4-12b-it.gguf"),
        help="GGUF judge model path",
    )
    parser.add_argument("--model", default="gemma4-12b")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--threads", type=int, default=default_cpu_threads())
    parser.add_argument(
        "--show-server-output",
        action="store_true",
        help="show llama-server logs (hidden by default)",
    )
    parser.add_argument("--startup-timeout", type=float, default=600)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    try:
        answer_model = model_name_from_dataset(args.input)
        candidate = read_tsv(
            args.input, separator=",", required_columns=CANDIDATE_COLUMNS
        )
        reference = read_tsv(args.reference, required_columns=REFERENCE_COLUMNS)
        candidate, reference = align_and_compare(candidate, reference)
        model_path = resolve_model_path(args.gguf)
    except (OSError, pd.errors.ParserError, ValueError) as error:
        parser.error(str(error))

    server = LlamaServer(
        LlamaServerConfig(
            model_path=model_path,
            cpu_server=args.cpu_server,
            port=args.port,
            parallel=args.parallel,
            threads=args.threads,
            show_output=args.show_server_output,
            context_size=args.context_size,
            alias=args.model,
            startup_timeout=args.startup_timeout,
            extra_args=("--reasoning", "off", "--reasoning-budget", "0"),
        )
    )
    server.start()
    try:
        run_evaluation(
            args, candidate, reference, answer_model, server.base_url, PROJECT_ROOT
        )
    finally:
        server.stop()


def run_evaluation(args, candidate, reference, answer_model, base_url, project_root):
    client = OpenAI(base_url=base_url, api_key="not-needed")

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
        project_root / "evaluation" / evaluation_filename(answer_model)
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
