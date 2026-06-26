"""Tests for auto-reporting eligibility (S3)."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.report_service import ReportPayload
from core.reported_sync import (
    auto_report_projects,
    build_reported_proposals,
    reported_hours_for_window,
    reported_issue_hours_for_window,
    split_auto_confirm,
    window_days,
)
from core.reported_time import ReportedTimeRecord, append_record


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


def _payload(day_from: str, day_to: str) -> ReportPayload:
    return ReportPayload(
        dt_from=datetime.fromisoformat(f"{day_from}T09:00:00"),
        dt_to=datetime.fromisoformat(f"{day_to}T17:00:00"),
        profiles=[], config_path=None, worklog_path=None,  # type: ignore[arg-type]
        all_events=[], included_events=[], grouped={}, overall_days={},
        project_reports={}, screen_time_days=None, collector_status={},
        args=Namespace(min_session=15, min_session_passive=5),
        source_strategy_effective="worklog-first",
    )


class ReportedWindowTests(unittest.TestCase):
    """D4 adoption switch: confirmed reported_time in-window flips sync to reported-mode."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _confirm(self, project, day, hours, *, state="confirmed"):
        append_record(
            ReportedTimeRecord(
                date=day, project=project, hours=hours, source="session",
                state=state, origin_ref=[f"{day}T0900"],
            ),
            home=self.home,
        )

    def test_window_days_is_inclusive(self):
        self.assertEqual(
            window_days(_payload("2026-06-23", "2026-06-25")),
            ["2026-06-23", "2026-06-24", "2026-06-25"],
        )

    def test_none_when_no_reported_time(self):
        self.assertIsNone(reported_hours_for_window(_payload("2026-06-23", "2026-06-23"), self.home))

    def test_returns_confirmed_hours_in_window(self):
        self._confirm("Alpha", "2026-06-24", 3.0)
        hours = reported_hours_for_window(_payload("2026-06-23", "2026-06-25"), self.home)
        self.assertEqual(hours, {("Alpha", "2026-06-24"): 3.0})

    def test_excludes_out_of_window_and_unconfirmed(self):
        self._confirm("Alpha", "2026-07-01", 3.0)  # out of window
        self._confirm("Beta", "2026-06-24", 2.0, state="proposed")  # not confirmed
        self.assertIsNone(reported_hours_for_window(_payload("2026-06-23", "2026-06-25"), self.home))

    def test_issue_view_keys_by_issue(self):
        # Phase 3b: the issue-aware view keeps the per-issue split.
        append_record(ReportedTimeRecord(date="2026-06-24", project="Alpha", hours=2.0, source="session",
                                         state="confirmed", origin_ref=["x"], issue_key="KAN-2"), home=self.home)
        append_record(ReportedTimeRecord(date="2026-06-24", project="Alpha", hours=3.0, source="session",
                                         state="confirmed", origin_ref=["y"], issue_key="KAN-3"), home=self.home)
        view = reported_issue_hours_for_window(_payload("2026-06-23", "2026-06-25"), self.home)
        self.assertEqual(view, {("Alpha", "2026-06-24", "KAN-2"): 2.0, ("Alpha", "2026-06-24", "KAN-3"): 3.0})


def _session_payload(day: str, project: str):
    # tz-aware throughout to match the production shape (load_commit_tags and the
    # report pipeline both yield aware datetimes).
    start = datetime.fromisoformat(f"{day}T10:00:00+00:00")
    end = datetime.fromisoformat(f"{day}T11:00:00+00:00")
    return ReportPayload(
        dt_from=datetime.fromisoformat(f"{day}T00:00:00+00:00"),
        dt_to=datetime.fromisoformat(f"{day}T23:59:00+00:00"),
        profiles=[], config_path=None, worklog_path=None,  # type: ignore[arg-type]
        all_events=[], included_events=[], grouped={},
        overall_days={day: {"sessions": [(start, end, [{"project": project, "source": "TIMELOG.md"}])], "hours": 1.0}},
        project_reports={}, screen_time_days=None, collector_status={},
        args=Namespace(min_session=15, min_session_passive=5),
        source_strategy_effective="worklog-first",
    )


class ProposalIssueStampTests(unittest.TestCase):
    """Phase 3b: build_reported_proposals stamps the git-inferred issue per session."""

    def test_stamps_issue_key_from_git_commit(self):
        report = _session_payload("2026-04-10", "Alpha")
        commit = SimpleNamespace(
            committed_at=datetime(2026, 4, 10, 10, 30, tzinfo=timezone.utc), subject="KAN-7 work"
        )
        with patch("core.jira_sync.load_commit_tags", return_value=[commit]), patch(
            "core.jira_sync.load_current_branch_issue_key", return_value=None
        ):
            proposals = build_reported_proposals(report, Path("."))
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].issue_key, "KAN-7")

    def test_no_repo_leaves_issue_key_none(self):
        report = _session_payload("2026-04-10", "Alpha")
        proposals = build_reported_proposals(report)
        self.assertEqual(len(proposals), 1)
        self.assertIsNone(proposals[0].issue_key)


if __name__ == "__main__":
    unittest.main()
