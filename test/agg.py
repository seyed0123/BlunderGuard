#!/usr/bin/env python3
from pathlib import Path
import re
import pandas as pd


ROOT = Path(".")
OUTPUT_FILE = Path("test_dataset.tsv")

COLUMNS = [
    "row_id",
    "before_fen",
    "after_fen",
    "move",
    "prompt",
    "analyse",
    "analyser",
    "move type",
    "move evaluation",
]


def extract_type(path: Path) -> str:
    """
    Extract type from file name.

    Examples:
        selected_advanced_moves.tsv -> advanced
        selected_intermediate_moves.tsv -> intermediate
        selected_noob_moves.tsv -> noob
    """

    match = re.search(r"selected_(.+?)_moves\.tsv$", path.name)
    if match:
        return match.group(1)

    # Fallback: look for known type names in the file name
    match = re.search(r"(advanced|intermediate|noob)", path.name)
    if match:
        return match.group(1)

    # Final fallback: use parent folder name
    return path.parent.name


def main():
    # Use this if you only want the selected_*_moves.tsv files
    tsv_files = sorted(
        path
        for path in ROOT.rglob("selected_*_moves.tsv")
        if path.resolve() != OUTPUT_FILE.resolve()
    )

    # If you want ALL .tsv files instead, use this:
    #
    # tsv_files = sorted(
    #     path
    #     for path in ROOT.rglob("*.tsv")
    #     if path.resolve() != OUTPUT_FILE.resolve()
    # )

    if not tsv_files:
        raise SystemExit("No TSV files found.")

    frames = []

    for tsv_file in tsv_files:
        print(f"Reading: {tsv_file}")

        try:
            df = pd.read_csv(
                tsv_file,
                sep="\t",
                header=None,
                names=COLUMNS,
                dtype=str,
                keep_default_na=False,
            )

        except pd.errors.EmptyDataError:
            print(f"Skipping empty file: {tsv_file}")
            continue

        except pd.errors.ParserError as error:
            print(f"Failed to parse: {tsv_file}")
            print(error)
            continue

        # Add the new column from the file name
        df["type"] = extract_type(tsv_file)

        frames.append(df)

    if not frames:
        raise SystemExit("No data was loaded.")

    combined = pd.concat(frames, ignore_index=True)

    combined.to_csv(
        OUTPUT_FILE,
        sep="\t",
        index=False,
        encoding="utf-8",
    )

    print()
    print("Done.")
    print(f"Files processed: {len(frames)}")
    print(f"Total rows:      {len(combined)}")
    print(f"Output file:     {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()