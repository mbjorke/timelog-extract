"""Backward-compatible wrapper; prefer `core.calibration.reconciliation`."""

from core.calibration.reconciliation import (
    ReconciliationResult,
    GroupReconciliationResult,
    evaluate_reconciliation,
)

__all__ = ["ReconciliationResult", "GroupReconciliationResult", "evaluate_reconciliation"]

