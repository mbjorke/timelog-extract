"""Tests for auto-reporting eligibility (S3)."""

from __future__ import annotations

import unittest

from core.reported_sync import auto_report_projects, split_auto_confirm
from core.reported_time import ReportedTimeRecord


def _proposal(project: str) -> ReportedTimeRecord:
    return ReportedTimeRecord(
        date="2026-06-18", project=project, hours=2.0, source="session",
        state="proposed", origin_ref=["2026-06-18T1000"],
    )


class AutoReportTests(unittest.TestCase):
    def test_auto_report_projects_reads_flag(self):
        profiles = [
            {"name": "Alpha", "auto_report": True},
            {"name": "Beta", "auto_report": False},
            {"name": "Gamma"},
        ]
        self.assertEqual(auto_report_projects(profiles), {"Alpha"})

    def test_eligible_project_is_confirmed(self):
        to_confirm, left = split_auto_confirm(
            [_proposal("Alpha")], [{"name": "Alpha", "auto_report": True}]
        )
        self.assertEqual(len(to_confirm), 1)
        self.assertEqual(to_confirm[0].state, "confirmed")
        self.assertEqual(to_confirm[0].project, "Alpha")
        self.assertEqual(to_confirm[0].origin_ref, ["2026-06-18T1000"])
        self.assertEqual(left, [])

    def test_non_optin_project_is_left_for_review(self):
        to_confirm, left = split_auto_confirm(
            [_proposal("Beta")], [{"name": "Beta", "auto_report": False}]
        )
        self.assertEqual(to_confirm, [])
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].state, "proposed")

    def test_uncategorized_never_auto_confirms(self):
        # Even if a profile somehow opts it in, Uncategorized is excluded.
        to_confirm, left = split_auto_confirm(
            [_proposal("Uncategorized")], [{"name": "Uncategorized", "auto_report": True}]
        )
        self.assertEqual(to_confirm, [])
        self.assertEqual(len(left), 1)


if __name__ == "__main__":
    unittest.main()
