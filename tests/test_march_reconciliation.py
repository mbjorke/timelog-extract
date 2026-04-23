from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from core.calibration.reconciliation import evaluate_reconciliation

DAY = "2026-03-10"
FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reconciliation" / "static_invoice_calibration.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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
        fixture = _fixture()
        group_name, group_data = next(iter(fixture["invoice_groups"].items()))
        project_alpha, project_beta = group_data["projects"]
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
                project_alpha: {DAY: {"hours": 15.0}},
                project_beta: {DAY: {"hours": 3.0}},
            },
            profiles=[
                {"name": project_alpha, "match_terms": ["alpha"], "tracked_urls": []},
                {"name": project_beta, "match_terms": ["beta"], "tracked_urls": []},
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
            fixture["ground_truth"],
            invoice_groups=fixture["invoice_groups"],
        )
        self.assertIn("group_summaries", payload)
        self.assertEqual(payload["primary_metric_mode"], "grouped")
        self.assertEqual(payload["primary_winner"], payload["winner_grouped"])
        self.assertIn("baseline", payload["group_summaries"])
        self.assertEqual(payload["group_rows"]["baseline"][0]["group"], group_name)


if __name__ == "__main__":
    unittest.main()

