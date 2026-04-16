from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace

from core.march_calibration import build_march_calibration_payload


class MarchCalibrationTests(unittest.TestCase):
    def test_build_payload_contains_reconciliation_and_screen_gap(self):
        ts = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Chrome",
                    "detail": "https://app.timeloggenius.dev/onboarding",
                    "project": "Uncategorized",
                    "timestamp": ts,
                }
            ],
            overall_days={"2026-03-10": {"hours": 2.0}},
            screen_time_days={"2026-03-10": 3.0 * 3600.0},
            project_reports={"Time Log Genius": {"2026-03-10": {"hours": 2.0}}},
            profiles=[
                {
                    "name": "Time Log Genius",
                    "match_terms": ["time log genius", "timelog"],
                    "tracked_urls": ["app.timeloggenius.dev"],
                }
            ],
            args=Namespace(
                exclude="",
                gap_minutes=15,
                min_session=15,
                min_session_passive=5,
            ),
        )
        payload = build_march_calibration_payload(
            report,
            {"Time Log Genius": 3.0},
            invoice_groups={
                "Internal": {"actual_hours": 3.0, "projects": ["Time Log Genius"]}
            },
        )
        self.assertIn("reconciliation", payload)
        self.assertIn("screen_time_gap", payload)
        self.assertIn(payload["winner_by_invoice_mae"], {"baseline", "A", "B", "C"})
        self.assertIn(payload["winner_by_grouped_invoice_mae"], {"baseline", "A", "B", "C"})
        self.assertEqual(payload["primary_metric_mode"], "grouped")
        self.assertEqual(payload["primary_winner"], payload["winner_by_grouped_invoice_mae"])


if __name__ == "__main__":
    unittest.main()

