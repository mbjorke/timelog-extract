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
    """
    Assemble a combined calibration payload containing reconciliation results and screen-time gap analysis.
    
    Parameters:
    	report (ReportPayload): The report data used for reconciliation and gap analysis.
    	ground_truth_hours (dict[str, float]): Mapping of invoice or project identifiers to ground-truth hours used for reconciliation.
    	invoice_groups (dict[str, dict[str, Any]] | None): Optional grouping of invoices forwarded to the reconciliation evaluation.
    
    Returns:
    	payload (dict[str, Any]): Payload with the following keys:
    		- winner_by_invoice_mae: Identifier of the winning estimator by invoice mean absolute error.
    		- winner_by_grouped_invoice_mae: Identifier of the winning estimator by grouped-invoice MAE (falls back to `winner_by_invoice_mae` if absent).
    		- primary_metric_mode: Metric mode used for selecting the primary winner (defaults to `"project"` if unspecified).
    		- primary_winner: Identifier of the primary winning estimator (falls back to `winner_by_invoice_mae` if unspecified).
    		- reconciliation: Full reconciliation result object returned by the reconciliation evaluation.
    		- screen_time_gap: Full result of the screen-time gap analysis.
    """
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

