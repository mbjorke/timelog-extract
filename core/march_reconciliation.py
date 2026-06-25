"""Backward-compatible wrapper; prefer `core.calibration.reconciliation`."""

from core.calibration.reconciliation import (
    GroupReconciliationResult,
    ReconciliationResult,
    evaluate_reconciliation,
)

__all__ = ["ReconciliationResult", "GroupReconciliationResult", "evaluate_reconciliation"]

