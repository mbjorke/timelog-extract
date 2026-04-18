"""Tests for Jira sync key resolution and aggregation."""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from core.jira_client import JiraCredentials, post_jira_worklog
from core.jira_sync import (
    build_jira_worklog_candidates,
    extract_issue_key,
)
from core.report_service import ReportPayload


class JiraSyncTests(unittest.TestCase):
    def test_extract_issue_key_from_text(self):
        self.assertEqual(extract_issue_key("ABC-123 fix api"), "ABC-123")
        self.assertIsNone(extract_issue_key("no key here"))

    def test_aggregate_candidates_per_issue_per_day(self):
        start = datetime(2026, 4, 10, 10, 0)
        mid = datetime(2026, 4, 10, 11, 0)
        end = datetime(2026, 4, 10, 12, 0)
        session_events_one = [{"project": "Project A", "source": "TIMELOG.md"}]
        session_events_two = [{"project": "Project B", "source": "TIMELOG.md"}]
        payload = ReportPayload(
            dt_from=start,
            dt_to=end,
            profiles=[],
            config_path=None,
            worklog_path=None,  # type: ignore[arg-type]
            all_events=[],
            included_events=[],
            grouped={},
            overall_days={
                "2026-04-10": {
                    "sessions": [
                        (start, mid, session_events_one),
                        (mid, end, session_events_two),
                    ],
                    "hours": 2.0,
                }
            },
            project_reports={},
            screen_time_days=None,
            collector_status={},
            args=Namespace(min_session=15, min_session_passive=5),
            source_strategy_effective="worklog-first",
        )
        with patch("core.jira_sync.load_commit_tags") as load_commits, patch(
            "core.jira_sync.load_current_branch_issue_key"
        ) as load_branch:
            load_commits.return_value = [
                SimpleNamespace(committed_at=start, subject="ABC-101 kickoff"),
                SimpleNamespace(committed_at=mid, subject="ABC-101 continue"),
            ]
            load_branch.return_value = "ABC-999"
            candidates, unresolved = build_jira_worklog_candidates(payload, PathLike("."))
        self.assertEqual(unresolved, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].issue_key, "ABC-101")
        self.assertEqual(candidates[0].day, "2026-04-10")
        self.assertGreater(candidates[0].seconds, 0)

    def test_post_jira_worklog_rejects_naive_started_timestamp(self):
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token="fake-token",
        )
        with self.assertRaises(RuntimeError):
            post_jira_worklog(
                creds=creds,
                issue_key="ABC-1",
                started=datetime(2026, 4, 10, 10, 0),
                time_spent_seconds=3600,
                comment="sync test",
            )


class PathLike:
    def __init__(self, value: str):
        self.value = value

    def __fspath__(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
