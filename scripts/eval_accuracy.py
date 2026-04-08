#!/usr/bin/env python3
"""
Evaluate report accuracy against a local golden dataset.

Usage:
  python3 scripts/eval_accuracy.py \
    --predictions docs/evals/predictions.json \
    --golden tests/fixtures/golden_dataset.json \
    --output docs/evals/latest.md
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def key_of(row: dict) -> tuple[str, str]:
    return str(row.get("date", "")).strip(), str(row.get("project", "")).strip()


def hours_of(row: dict) -> float:
    try:
        return float(row.get("hours", 0.0))
    except (TypeError, ValueError):
        return 0.0


def evaluate(predictions: list[dict], golden: list[dict]) -> dict:
    pred_map = {key_of(r): r for r in predictions}
    gold_map = {key_of(r): r for r in golden}

    keys = sorted(set(pred_map.keys()) | set(gold_map.keys()))
    total = len(keys)
    correct_project = 0
    uncategorized_count = 0
    hour_deltas = []
    mismatches = []

    for key in keys:
        pred = pred_map.get(key, {})
        gold = gold_map.get(key, {})
        pred_project = str(pred.get("project", "")).strip()
        gold_project = str(gold.get("project", "")).strip()

        if pred_project.lower() in {"okategoriserat", "uncategorized"}:
            uncategorized_count += 1
        if pred_project == gold_project:
            correct_project += 1

        pred_h = hours_of(pred)
        gold_h = hours_of(gold)
        delta = abs(pred_h - gold_h)
        baseline = max(gold_h, 1e-9)
        pct = (delta / baseline) * 100.0 if gold_h > 0 else (100.0 if pred_h > 0 else 0.0)
        hour_deltas.append(pct)

        if pred_project != gold_project or pct > 20.0:
            mismatches.append(
                {
                    "date": key[0],
                    "project": key[1],
                    "pred_project": pred_project,
                    "gold_project": gold_project,
                    "pred_hours": pred_h,
                    "gold_hours": gold_h,
                    "hour_delta_pct": round(pct, 1),
                }
            )

    attribution_accuracy = (correct_project / total * 100.0) if total else 0.0
    uncategorized_rate = (uncategorized_count / total * 100.0) if total else 0.0
    avg_hour_delta_pct = sum(hour_deltas) / len(hour_deltas) if hour_deltas else 0.0

    return {
        "total_rows": total,
        "attribution_accuracy_pct": round(attribution_accuracy, 2),
        "uncategorized_rate_pct": round(uncategorized_rate, 2),
        "avg_hour_delta_pct": round(avg_hour_delta_pct, 2),
        "mismatches": mismatches,
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Accuracy Evaluation",
        "",
        "## KPI Snapshot",
        "",
        f"- Rows evaluated: `{result['total_rows']}`",
        f"- Attribution accuracy: `{result['attribution_accuracy_pct']}%`",
        f"- Uncategorized rate: `{result['uncategorized_rate_pct']}%`",
        f"- Average hour delta: `{result['avg_hour_delta_pct']}%`",
        "",
        "## Mismatches (Top 20)",
        "",
        "| Date | Project Key | Predicted Project | Expected Project | Pred Hours | Gold Hours | Delta % |",
        "|---|---|---|---|---:|---:|---:|",
    ]

    for row in result["mismatches"][:20]:
        lines.append(
            f"| {row['date']} | {row['project']} | {row['pred_project']} | {row['gold_project']} | "
            f"{row['pred_hours']:.2f} | {row['gold_hours']:.2f} | {row['hour_delta_pct']:.1f} |"
        )

    if not result["mismatches"]:
        lines.append("| - | - | - | - | - | - | - |")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate timelog predictions against golden dataset.")
    parser.add_argument("--predictions", required=True, help="Path to predicted rows JSON")
    parser.add_argument("--golden", required=True, help="Path to golden rows JSON")
    parser.add_argument("--output", default="docs/evals/latest.md", help="Markdown output file path")
    args = parser.parse_args()

    pred_path = Path(args.predictions).expanduser()
    gold_path = Path(args.golden).expanduser()
    out_path = Path(args.output).expanduser()

    predictions = load_rows(pred_path)
    golden = load_rows(gold_path)
    result = evaluate(predictions, golden)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(result), encoding="utf-8")

    print(f"Evaluation complete. Wrote {out_path}")
    print(
        f"Accuracy={result['attribution_accuracy_pct']}%, "
        f"Uncategorized={result['uncategorized_rate_pct']}%, "
        f"AvgHourDelta={result['avg_hour_delta_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
