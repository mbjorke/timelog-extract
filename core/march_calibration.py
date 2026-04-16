"""Combined March calibration report helpers."""

from __future__ import annotations

from typing import Any

from core.march_reconciliation import evaluate_reconciliation
from core.screen_time_gap_analysis import analyze_screen_time_gaps


def build_march_calibration_payload(report, ground_truth_hours: dict[str, float]) -> dict[str, Any]:
    reconciliation = evaluate_reconciliation(report, ground_truth_hours)
    screen_time_gap = analyze_screen_time_gaps(report)
    return {
        "winner_by_invoice_mae": reconciliation["winner"],
        "reconciliation": reconciliation,
        "screen_time_gap": screen_time_gap,
    }

