import pytest

from app.artifact_naming import (
    dataset_filename,
    evaluation_filename,
    model_name_from_dataset,
)


def test_dataset_filename_round_trip():
    filename = dataset_filename("gemini-3.5-flash")

    assert filename == "chess_coach_dataset_complete__model_gemini-3.5-flash.csv"
    assert model_name_from_dataset(filename) == "gemini-3.5-flash"


def test_evaluation_filename_contains_answer_model():
    assert evaluation_filename("gpt-5.5") == "judged__model_gpt-5.5.json"


def test_dataset_filename_without_model_is_rejected():
    with pytest.raises(ValueError, match="candidate filename"):
        model_name_from_dataset("chess_coach_dataset_complete.csv")
