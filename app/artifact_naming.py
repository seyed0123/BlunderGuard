"""Naming conventions for generated datasets and evaluation reports."""

import re
from pathlib import Path


MODEL_MARKER = "__model_"
DEFAULT_DATASET_STEM = "chess_coach_dataset_complete"


def validate_model_name(model_name: str) -> str:
    """Return a filename-safe model name or raise a clear error."""
    model_name = model_name.strip()
    if not model_name:
        raise ValueError("model name cannot be empty")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", model_name):
        raise ValueError(
            "model name may contain only letters, numbers, dots, underscores, and hyphens"
        )
    return model_name


def dataset_filename(model_name: str, stem: str = DEFAULT_DATASET_STEM) -> str:
    """Build a candidate dataset filename containing its answer model."""
    return f"{stem}{MODEL_MARKER}{validate_model_name(model_name)}.csv"


def model_name_from_dataset(path: str | Path) -> str:
    """Extract the answer model from a conventionally named candidate CSV."""
    path = Path(path)
    stem = path.stem
    if MODEL_MARKER not in stem:
        raise ValueError(
            f"candidate filename must end with '{MODEL_MARKER}<model>.csv': {path.name}"
        )
    model_name = stem.rsplit(MODEL_MARKER, 1)[1]
    return validate_model_name(model_name)


def evaluation_filename(model_name: str) -> str:
    """Build the default JSON filename for a candidate model's evaluation."""
    return f"judged{MODEL_MARKER}{validate_model_name(model_name)}.json"
