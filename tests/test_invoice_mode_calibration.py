from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.report_aggregate import AggregationResult
from core.report_service import _apply_invoice_calibration_if_requested

REPORT_DT_TO = datetime(2026, 3, 31, tzinfo=timezone.utc)
FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reconciliation" / "static_invoice_calibration.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class InvoiceModeCalibrationTests(unittest.TestCase):
    def _agg(self) -> AggregationResult:
        fixture = _fixture()
        return AggregationResult(
            all_events=[{"project": "Uncategorized", "source": "Chrome", "detail": "x"}],
            included_events=[],
            grouped={},
            overall_days={},
            project_reports=fixture["project_reports"],
        )

    def test_calibrated_a_overwrites_project_hours_from_reconciliation(self):
        fixture = _fixture()
        report_day = fixture["day"]
        group = next(iter(fixture["invoice_groups"].values()))
        project_alpha = group["projects"][0]
        project_beta = group["projects"][1]
        with tempfile.TemporaryDirectory() as tmp:
            truth_path = Path(tmp) / "truth.json"
            truth_path.write_text(
                json.dumps(
                    {
                        "projects": fixture["ground_truth"],
                        "invoice_groups": fixture["invoice_groups"],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(invoice_mode="calibrated-a", invoice_ground_truth=str(truth_path))
            with patch("core.report_service.evaluate_reconciliation") as reco:
                reco.return_value = {
                    "rows": {
                        "A": fixture["mock_reconciliation_rows_a"]
                    }
                }
                out = _apply_invoice_calibration_if_requested(
                    agg=self._agg(),
                    args=args,
                    profiles=[{"name": project_alpha}, {"name": project_beta}],
                    dt_to=REPORT_DT_TO,
                )
            self.assertAlmostEqual(out.project_reports[project_alpha][report_day]["hours"], 13.95, places=6)
            self.assertAlmostEqual(out.project_reports[project_beta][report_day]["hours"], 4.92, places=6)

    def test_baseline_mode_keeps_original_aggregation(self):
        args = argparse.Namespace(invoice_mode="baseline", invoice_ground_truth="march_invoice_ground_truth.json")
        agg = self._agg()
        out = _apply_invoice_calibration_if_requested(
            agg=agg,
            args=args,
            profiles=[],
            dt_to=REPORT_DT_TO,
        )
        self.assertEqual(out.project_reports, agg.project_reports)


if __name__ == "__main__":
    unittest.main()

