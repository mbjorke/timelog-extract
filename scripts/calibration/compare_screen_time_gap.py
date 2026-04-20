#!/usr/bin/env python3
"""Compare two screen-time gap analysis payloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TOTAL_KEYS = [
    "estimated_hours",
    "screen_time_hours",
    "coverage_ratio",
    "unexplained_screen_time_hours",
    "over_attributed_hours",
]


def load_payload(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object payload")
    if "totals" not in data or "days" not in data:
        raise ValueError(f"{path} missing required keys: totals/days")
    return data


def _as_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def compare_totals(old_payload: dict, new_payload: dict) -> list[tuple[str, float, float, float]]:
    old_totals = old_payload.get("totals", {})
    new_totals = new_payload.get("totals", {})
    rows = []
    for key in TOTAL_KEYS:
        old_value = _as_float(old_totals.get(key, 0.0))
        new_value = _as_float(new_totals.get(key, 0.0))
        rows.append((key, old_value, new_value, new_value - old_value))
    return rows


def render_report(old_path: Path, new_path: Path, old_payload: dict, new_payload: dict) -> str:
    lines = [
        "Screen Time Gap Comparison",
        f"- Old: {old_path}",
        f"- New: {new_path}",
        "",
        "Totals delta (new - old):",
    ]
    for key, old_value, new_value, delta in compare_totals(old_payload, new_payload):
        lines.append(f"- {key}: {old_value:.4f} -> {new_value:.4f} (delta {delta:+.4f})")
    old_days = len(old_payload.get("days", []))
    new_days = len(new_payload.get("days", []))
    lines.append("")
    lines.append(f"Day rows: {old_days} -> {new_days} (delta {new_days - old_days:+d})")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two out/reconciliation/screen_time_gap.json payloads."
    )
    parser.add_argument("--old", required=True, help="Path to previous payload JSON")
    parser.add_argument("--new", required=True, help="Path to current payload JSON")
    args = parser.parse_args()

    old_path = Path(args.old).expanduser()
    new_path = Path(args.new).expanduser()
    old_payload = load_payload(old_path)
    new_payload = load_payload(new_path)
    print(render_report(old_path, new_path, old_payload, new_payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
