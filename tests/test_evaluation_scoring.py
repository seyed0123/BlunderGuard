import json
from types import SimpleNamespace

import pandas as pd
import pytest

from evaluation.judge_responses import (
    EXPECTED_COLUMNS,
    calculate_overall,
    judge,
    parse_judge_response,
    read_tsv,
)
from evaluation.judge_responses import recover_scores_from_malformed_response


def test_calculate_overall_uses_weighted_formula():
    scores = {
        "correctness": 8,
        "faithfulness": 6,
        "helpfulness": 7,
        "instruction_following": 9,
        "fluency": 5,
    }

    assert calculate_overall(scores) == 7.1


def test_calculate_overall_rejects_missing_component():
    scores = {
        "correctness": 8,
        "faithfulness": 6,
        "helpfulness": 7,
        "instruction_following": 9,
    }

    assert calculate_overall(scores) is None


def test_parse_judge_response_validates_and_calculates_overall():
    response = json.dumps(
        {
            "correctness": 8,
            "instruction_following": 9,
            "helpfulness": 7,
            "faithfulness": 6,
            "fluency": 5,
            "reason": "Mostly accurate explanation",
        }
    )

    scores = parse_judge_response(response)

    assert scores["overall"] == 7.1
    assert scores["reason"] == "Mostly accurate explanation"


def test_parse_judge_response_rejects_unquoted_reason():
    malformed = (
        '{"correctness":8,"instruction_following":9,"helpfulness":7,'
        '"faithfulness":6,"fluency":5,"reason":Mostly accurate}'
    )

    with pytest.raises(json.JSONDecodeError):
        parse_judge_response(malformed)


def test_parse_judge_response_rejects_out_of_range_score():
    response = json.dumps(
        {
            "correctness": 11,
            "instruction_following": 9,
            "helpfulness": 7,
            "faithfulness": 6,
            "fluency": 5,
            "reason": "Score outside range",
        }
    )

    with pytest.raises(ValueError, match="correctness"):
        parse_judge_response(response)


def test_judge_keeps_invalid_raw_output_out_of_reason():
    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            message = SimpleNamespace(content='{"correctness": 8, "reason": broken}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    completions = FakeCompletions()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    scores = judge(client, "candidate", "reference", "judge-model")

    assert completions.calls == 3
    assert scores["reason"] == "Invalid judge response"
    assert scores["raw_response"] == '{"correctness": 8, "reason": broken}'
    assert scores["overall"] is None


def test_recover_scores_when_only_reason_is_unquoted():
    malformed = """{
    "correctness": 0,
    "instruction_following": 1,
    "helpfulness": 0,
    "faithfulness": 0,
    "fluency": 1,
    "reason": Opposite of reference analysis."
    }"""

    scores = recover_scores_from_malformed_response(malformed)

    assert scores["correctness"] == 0
    assert scores["instruction_following"] == 1
    assert scores["fluency"] == 1
    assert scores["overall"] == 0.2
    assert scores["reason"] == "Recovered malformed response"


def test_read_tsv_allows_extra_candidate_columns(tmp_path):
    row = {column: f"value-{column}" for column in EXPECTED_COLUMNS}
    row.update({"status": "SUCCESS", "latency_ms": "120"})
    path = tmp_path / "candidate.csv"
    pd.DataFrame([row]).to_csv(path, index=False)

    dataframe = read_tsv(path, separator=",")

    assert list(dataframe.columns) == EXPECTED_COLUMNS + ["status", "latency_ms"]


def test_read_tsv_rejects_missing_required_columns(tmp_path):
    row = {
        column: f"value-{column}"
        for column in EXPECTED_COLUMNS
        if column != "analyse"
    }
    path = tmp_path / "candidate.csv"
    pd.DataFrame([row]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns.*analyse"):
        read_tsv(path, separator=",")
