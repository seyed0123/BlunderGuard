from pathlib import Path

from evaluation.aggregate_results import extract_type


def test_extract_type_uses_noob_for_beginner_input_file():
    path = Path("evaluation/beginner/selected_beginner_moves.tsv")

    assert extract_type(path) == "noob"


def test_extract_type_preserves_other_difficulty_names():
    path = Path("evaluation/advanced/selected_advanced_moves.tsv")

    assert extract_type(path) == "advanced"
