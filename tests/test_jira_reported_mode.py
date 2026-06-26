"""Phase 3: jira-sync reads confirmed reported_time mapped via jira_issue_key."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core.jira_sync import build_jira_worklog_candidates
from core.report_service import ReportPayload
from core.reported_time import ReportedTimeRecord, append_record


def _reported_payload(day: str) -> ReportPayload:
    """A minimal report whose window covers ``day`` (no observed sessions needed)."""
    return ReportPayload(
        dt_from=datetime.fromisoformat(f"{day}T09:00:00"),
        dt_to=datetime.fromisoformat(f"{day}T17:00:00"),
        profiles=[], config_path=None, worklog_path=None,  # type: ignore[arg-type]
        all_events=[], included_events=[], grouped={}, overall_days={},
        project_reports={}, screen_time_days=None, collector_status={},
        args=Namespace(min_session=15, min_session_passive=5),
        source_strategy_effective="worklog-first",
    )


class JiraReportedModeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _confirm(self, project, day, hours, issue_key=None):
        append_record(
            ReportedTimeRecord(
                date=day, project=project, hours=hours, source="session",
                state="confirmed", origin_ref=[f"{day}T{int(hours * 100):04d}"],
                issue_key=issue_key,
            ),
            home=self.home,
        )

    def test_maps_project_to_jira_issue_key_without_git(self):
        self._confirm("Project A", "2026-04-10", 4.0)
        payload = _reported_payload("2026-04-10")
        profiles = [{"name": "Project A", "jira_issue_key": "ABC-101"}]
        # In reported-mode git must not be consulted; the side_effect fails loudly.
        with patch("core.jira_sync.load_commit_tags", side_effect=AssertionError("git consulted")):
            candidates, unresolved = build_jira_worklog_candidates(
                payload, Path("."), profiles, home=self.home
            )
        self.assertEqual(unresolved, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].issue_key, "ABC-101")
        self.assertEqual(candidates[0].seconds, 4 * 3600)
        self.assertEqual(candidates[0].source, "reported")
        self.assertIn(candidates[0].marker, candidates[0].comment)

    def test_project_without_issue_key_is_unresolved(self):
        self._confirm("Project A", "2026-04-10", 4.0)
        payload = _reported_payload("2026-04-10")
        candidates, unresolved = build_jira_worklog_candidates(
            payload, Path("."), [{"name": "Project A"}], home=self.home
        )
        self.assertEqual(candidates, [])
        self.assertEqual(unresolved, 1)

    def test_two_issues_one_project_day_become_two_worklogs(self):
        # Phase 3b: per-session issue_key keeps the split — two issues, two worklogs.
        self._confirm("Project A", "2026-04-10", 2.0, issue_key="KAN-2")
        self._confirm("Project A", "2026-04-10", 3.0, issue_key="KAN-3")
        payload = _reported_payload("2026-04-10")
        with patch("core.jira_sync.load_commit_tags", side_effect=AssertionError("git consulted")):
            candidates, unresolved = build_jira_worklog_candidates(
                payload, Path("."), [{"name": "Project A"}], home=self.home
            )
        self.assertEqual(unresolved, 0)
        by_issue = {c.issue_key: c.seconds for c in candidates}
        self.assertEqual(by_issue, {"KAN-2": 2 * 3600, "KAN-3": 3 * 3600})

    def test_record_issue_key_wins_over_profile_fallback(self):
        self._confirm("Project A", "2026-04-10", 2.0, issue_key="KAN-9")
        payload = _reported_payload("2026-04-10")
        # Profile says ABC-101, but the record's own issue_key must win.
        candidates, _unresolved = build_jira_worklog_candidates(
            payload, Path("."), [{"name": "Project A", "jira_issue_key": "ABC-101"}], home=self.home
        )
        self.assertEqual([c.issue_key for c in candidates], ["KAN-9"])

    def test_no_record_issue_falls_back_to_profile(self):
        self._confirm("Project A", "2026-04-10", 2.0)  # no per-session issue
        payload = _reported_payload("2026-04-10")
        candidates, _unresolved = build_jira_worklog_candidates(
            payload, Path("."), [{"name": "Project A", "jira_issue_key": "ABC-101"}], home=self.home
        )
        self.assertEqual([c.issue_key for c in candidates], ["ABC-101"])


if __name__ == "__main__":
    unittest.main()
