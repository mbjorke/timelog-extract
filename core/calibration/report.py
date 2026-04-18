"""Combined March calibration report helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.calibration.reconciliation import evaluate_reconciliation
from core.calibration.screen_time_gap import analyze_screen_time_gaps

if TYPE_CHECKING:
    from core.report_service import ReportPayload


def build_march_calibration_payload(
    report: ReportPayload,
    ground_truth_hours: dict[str, float],
    invoice_groups: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reconciliation = evaluate_reconciliation(report, ground_truth_hours, invoice_groups=invoice_groups)
    screen_time_gap = analyze_screen_time_gaps(report)
    return {
        "winner_by_invoice_mae": reconciliation["winner"],
        "winner_by_grouped_invoice_mae": reconciliation.get("winner_grouped", reconciliation["winner"]),
        "primary_metric_mode": reconciliation.get("primary_metric_mode", "project"),
        "primary_winner": reconciliation.get("primary_winner", reconciliation["winner"]),
        "reconciliation": reconciliation,
        "screen_time_gap": screen_time_gap,
    }

