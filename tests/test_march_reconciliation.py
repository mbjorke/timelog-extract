from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace

from core.march_reconciliation import evaluate_reconciliation


class MarchReconciliationTests(unittest.TestCase):
    def test_evaluate_reconciliation_returns_variants_and_winner(self):
        ts = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Chrome",
                    "detail": "https://app.timeloggenius.dev/onboarding",
                    "project": "Uncategorized",
                    "timestamp": ts,
                },
                {
                    "source": "Chrome",
                    "detail": "https://ops.example.com/pager",
                    "project": "Uncategorized",
                    "timestamp": ts,
                },
            ],
            project_reports={
                "Time Log Genius": {"2026-03-10": {"hours": 2.0}},
                "Internal Ops": {"2026-03-10": {"hours": 1.0}},
            },
            profiles=[
                {
                    "name": "Time Log Genius",
                    "match_terms": ["time log genius", "timelog"],
                    "tracked_urls": ["app.timeloggenius.dev"],
                },
                {
                    "name": "Internal Ops",
                    "match_terms": ["ops"],
                    "tracked_urls": ["ops.example.com"],
                },
            ],
            args=Namespace(
                exclude="",
                gap_minutes=15,
                min_session=15,
                min_session_passive=5,
            ),
        )
        ground_truth = {
            "Time Log Genius": 3.0,
            "Internal Ops": 1.5,
        }
        payload = evaluate_reconciliation(report, ground_truth)
        self.assertIn(payload["winner"], {"baseline", "A", "B", "C"})
        self.assertEqual(set(payload["summaries"].keys()), {"baseline", "A", "B", "C"})
        self.assertEqual(len(payload["rows"]["baseline"]), 2)


if __name__ == "__main__":
    unittest.main()

