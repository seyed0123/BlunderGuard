#!/usr/bin/env python3
"""Create comparison plots from one or more judged model JSON files.

Run from the repository root:

    python -m evaluation.plot_judged_results

By default, every ``evaluation/judged__model_*.json`` file is read and plots
are written to ``evaluation/plots``. Paths and the output directory can also
be supplied on the command line.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "blunderguard-matplotlib"))

import matplotlib

matplotlib.use("Agg")  # Works on servers and CI machines without a display.
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
DEFAULT_PATTERN = "judged__model_*.json"
METRICS = (
    "correctness",
    "instruction_following",
    "helpfulness",
    "faithfulness",
    "fluency",
    "overall",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help=f"Judged JSON files (default: evaluation/{DEFAULT_PATTERN})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "plots",
        help="Directory in which PNG plots and summary.csv are saved",
    )
    parser.add_argument("--dpi", type=int, default=180, help="PNG resolution")
    return parser.parse_args()


def numeric(value: object) -> float | None:
    """Return a finite float, or None for missing/invalid score values."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_results(paths: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict) or not isinstance(document.get("results"), list):
            raise ValueError(f"{path}: expected a JSON object containing a results array")

        model = str(document.get("answer_model") or document.get("model") or path.stem)
        for result in document["results"]:
            if not isinstance(result, dict) or not isinstance(result.get("scores"), dict):
                continue
            scores = result["scores"]
            record: dict[str, object] = {
                "model": model,
                "category": str(result.get("type") or "unknown"),
                "row_id": result.get("row_id"),
                "parse_error": bool(scores.get("parse_error")),
            }
            record.update({metric: numeric(scores.get(metric)) for metric in METRICS})
            records.append(record)
    if not records:
        raise ValueError("No valid result records were found in the input files")
    return records


def values(records: Iterable[dict[str, object]], metric: str) -> list[float]:
    return [value for row in records if (value := numeric(row.get(metric))) is not None]


def ordered_unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def grouped_bar(
    series: dict[str, list[float]],
    groups: list[str],
    title: str,
    ylabel: str,
    output: Path,
    dpi: int,
) -> None:
    labels = list(series)
    width = min(0.8 / max(len(labels), 1), 0.22)
    fig, ax = plt.subplots(figsize=(max(9, len(groups) * 1.45), 5.5))
    centers = list(range(len(groups)))
    offset0 = -(len(labels) - 1) * width / 2
    for index, label in enumerate(labels):
        positions = [center + offset0 + index * width for center in centers]
        bars = ax.bar(positions, series[label], width=width, label=label)
        ax.bar_label(bars, fmt="%.2f", fontsize=7, padding=2, rotation=90)
    ax.set(title=title, ylabel=ylabel, xticks=centers, xticklabels=groups)
    ax.set_ylim(0, 10.8)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncols=min(3, len(labels)))
    fig.tight_layout()
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_metric_means(records: list[dict[str, object]], output: Path, dpi: int) -> None:
    models = ordered_unique(str(row["model"]) for row in records)
    series = {
        model: [mean(values((r for r in records if r["model"] == model), metric)) for metric in METRICS]
        for model in models
    }
    grouped_bar(series, list(METRICS), "Mean score by evaluation metric", "Mean score (0–10)", output, dpi)


def plot_categories(records: list[dict[str, object]], output: Path, dpi: int) -> None:
    models = ordered_unique(str(row["model"]) for row in records)
    categories = sorted({str(row["category"]) for row in records})
    series: dict[str, list[float]] = {}
    for model in models:
        model_means = []
        for category in categories:
            subset = (r for r in records if r["model"] == model and r["category"] == category)
            scores = values(subset, "overall")
            model_means.append(mean(scores) if scores else 0.0)
        series[model] = model_means
    grouped_bar(series, categories, "Overall score by difficulty/category", "Mean overall score (0–10)", output, dpi)


def plot_distributions(records: list[dict[str, object]], output: Path, dpi: int) -> None:
    models = ordered_unique(str(row["model"]) for row in records)
    distributions = [values((r for r in records if r["model"] == model), "overall") for model in models]
    fig, ax = plt.subplots(figsize=(max(7, len(models) * 1.5), 5.5))
    boxes = ax.boxplot(distributions, tick_labels=models, patch_artist=True, showmeans=True)
    for box in boxes["boxes"]:
        box.set_facecolor("#4c78a8")
        box.set_alpha(0.65)
    ax.set(title="Distribution of overall scores", ylabel="Overall score (0–10)")
    ax.set_ylim(-0.25, 10.5)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return float("nan")
    x_mean, y_mean = mean(xs), mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys))
    return numerator / denominator if denominator else float("nan")


def plot_correlation(records: list[dict[str, object]], output: Path, dpi: int) -> None:
    metrics = list(METRICS[:-1])
    matrix: list[list[float]] = []
    for left in metrics:
        row = []
        for right in metrics:
            pairs = [(numeric(r.get(left)), numeric(r.get(right))) for r in records]
            valid = [(x, y) for x, y in pairs if x is not None and y is not None]
            row.append(correlation([x for x, _ in valid], [y for _, y in valid]))
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(7.5, 6))
    image = ax.imshow(matrix, vmin=-1, vmax=1, cmap="coolwarm")
    short = [metric.replace("instruction_following", "instruction") for metric in metrics]
    ax.set_xticks(range(len(short)), labels=short, rotation=35, ha="right")
    ax.set_yticks(range(len(short)), labels=short)
    ax.set_title("Correlation between judge metrics (all models)")
    for y, row in enumerate(matrix):
        for x, score in enumerate(row):
            ax.text(x, y, "n/a" if math.isnan(score) else f"{score:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_summary(records: list[dict[str, object]], output: Path) -> None:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        groups[(str(record["model"]), str(record["category"]))].append(record)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "category", "rows", "parse_errors", *[f"mean_{m}" for m in METRICS]])
        for (model, category), rows in groups.items():
            metric_means = []
            for metric in METRICS:
                scores = values(rows, metric)
                metric_means.append(round(mean(scores), 4) if scores else "")
            writer.writerow([model, category, len(rows), sum(bool(r["parse_error"]) for r in rows), *metric_means])


def main() -> None:
    args = parse_args()
    paths = args.files or sorted(ROOT.glob(DEFAULT_PATTERN))
    if not paths:
        raise SystemExit(f"No files supplied and none matched {ROOT / DEFAULT_PATTERN}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit("Input file(s) not found: " + ", ".join(missing))

    records = load_results(paths)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_metric_means(records, args.output_dir / "01_metric_means.png", args.dpi)
    plot_categories(records, args.output_dir / "02_category_comparison.png", args.dpi)
    plot_distributions(records, args.output_dir / "03_overall_distributions.png", args.dpi)
    plot_correlation(records, args.output_dir / "04_metric_correlations.png", args.dpi)
    save_summary(records, args.output_dir / "summary.csv")
    print(f"Read {len(records)} judged responses from {len(paths)} file(s).")
    print(f"Saved plots and summary to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
