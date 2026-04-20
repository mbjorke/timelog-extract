from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace

from core.calibration.reconciliation import evaluate_reconciliation


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
                "Product Suite": {"2026-03-10": {"hours": 2.0}},
                "Internal Ops": {"2026-03-10": {"hours": 1.0}},
            },
            profiles=[
                {
                    "name": "Product Suite",
                    "match_terms": ["product suite", "tracker"],
                    "tracked_urls": ["app.productsuite.dev"],
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
            "Product Suite": 3.0,
            "Internal Ops": 1.5,
        }
        payload = evaluate_reconciliation(report, ground_truth)
        self.assertIn(payload["winner"], {"baseline", "A", "B", "C"})
        self.assertEqual(payload["primary_metric_mode"], "project")
        self.assertEqual(payload["primary_winner"], payload["winner"])
        self.assertEqual(set(payload["summaries"].keys()), {"baseline", "A", "B", "C"})
        self.assertEqual(len(payload["rows"]["baseline"]), 2)

    def test_grouped_invoice_summary_is_included(self):
        ts = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Chrome",
                    "detail": "https://app.productsuite.dev/onboarding",
                    "project": "Uncategorized",
                    "timestamp": ts,
                }
            ],
            project_reports={
                "ÅSS: Membra": {"2026-03-10": {"hours": 15.0}},
                "ÅSS: Nav": {"2026-03-10": {"hours": 3.0}},
            },
            profiles=[
                {"name": "ÅSS: Membra", "match_terms": ["membra"], "tracked_urls": []},
                {"name": "ÅSS: Nav", "match_terms": ["nav"], "tracked_urls": []},
            ],
            args=Namespace(
                exclude="",
                gap_minutes=15,
                min_session=15,
                min_session_passive=5,
            ),
        )
        payload = evaluate_reconciliation(
            report,
            {"ÅSS: Membra": 10.75, "ÅSS: Nav": 8.0},
            invoice_groups={
                "ÅSS": {"actual_hours": 18.75, "projects": ["ÅSS: Membra", "ÅSS: Nav"]}
            },
        )
        self.assertIn("group_summaries", payload)
        self.assertEqual(payload["primary_metric_mode"], "grouped")
        self.assertEqual(payload["primary_winner"], payload["winner_grouped"])
        self.assertIn("baseline", payload["group_summaries"])
        self.assertEqual(payload["group_rows"]["baseline"][0]["group"], "ÅSS")


if __name__ == "__main__":
    unittest.main()

