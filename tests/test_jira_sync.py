"""Tests for Jira sync key resolution and aggregation."""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from collectors.jira import JiraCredentials, post_jira_worklog
from core.cli import app
from core.jira_sync import (
    JiraWorklogCandidate,
    build_jira_worklog_candidates,
    extract_issue_key,
)
from core.report_service import ReportPayload
from typer.testing import CliRunner

TEST_API_PLACEHOLDER = "fake-token"


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
            api_token=TEST_API_PLACEHOLDER,
        )
        with self.assertRaises(RuntimeError):
            post_jira_worklog(
                creds=creds,
                issue_key="ABC-1",
                started=datetime(2026, 4, 10, 10, 0),
                time_spent_seconds=3600,
                comment="sync test",
            )

    def test_branch_key_used_when_no_commit_key_in_window(self):
        start = datetime(2026, 4, 10, 10, 0)
        end = datetime(2026, 4, 10, 11, 0)
        payload = ReportPayload(
            dt_from=start,
            dt_to=end,
            profiles=[],
            config_path=None,
            worklog_path=None,  # type: ignore[arg-type]
            all_events=[],
            included_events=[],
            grouped={},
            overall_days={"2026-04-10": {"sessions": [(start, end, [{"project": "Demo"}])], "hours": 1.0}},
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
                SimpleNamespace(committed_at=datetime(2026, 4, 9, 8, 0), subject="ABC-1 old")
            ]
            load_branch.return_value = "ABC-2"
            candidates, unresolved = build_jira_worklog_candidates(payload, PathLike("."))
        self.assertEqual(unresolved, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].issue_key, "ABC-2")
        self.assertEqual(candidates[0].source, "branch")

    def test_cli_jira_sync_hides_branch_candidate_when_commit_exists_same_day(self):
        runner = CliRunner()
        candidate_branch = JiraWorklogCandidate(
            issue_key="XYZ-123",
            day="2026-04-20",
            started=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
            seconds=3600,
            projects=["Demo"],
            source="branch",
        )
        candidate_commit = JiraWorklogCandidate(
            issue_key="ABC-1",
            day="2026-04-20",
            started=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            seconds=7200,
            projects=["Demo"],
            source="commit",
        )
        fake_report = SimpleNamespace()
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        with patch("core.report_service.run_timelog_report", return_value=fake_report), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=creds), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates",
            return_value=([candidate_branch, candidate_commit], 0),
        ), patch("core.cli_jira_sync.post_candidate", return_value="10001"):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on", "--dry-run"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertNotIn("XYZ-123", result.output)
        self.assertIn("ABC-1", result.output)
        self.assertIn("Jira sync summary: posted=0, skipped=2, unresolved=0, failed=0", result.output)
        self.assertIn("Next: rerun with confirmation", result.output)

    def test_cli_jira_sync_summary_counts_failure_hint(self):
        runner = CliRunner()
        candidate = JiraWorklogCandidate(
            issue_key="ABC-1",
            day="2026-04-20",
            started=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            seconds=7200,
            projects=["Demo"],
            source="commit",
        )
        fake_report = SimpleNamespace()
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        with patch("core.report_service.run_timelog_report", return_value=fake_report), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=creds), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates",
            return_value=([candidate], 0),
        ), patch("core.cli_jira_sync.typer.confirm", return_value=True), patch(
            "core.cli_jira_sync.post_candidate", side_effect=RuntimeError("Jira HTTP 404")
        ):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Jira sync summary: posted=0, skipped=0, unresolved=0, failed=1", result.output)
        self.assertIn("Next: verify Jira credentials and issue visibility", result.output)


class PathLike:
    def __init__(self, value: str):
        self.value = value

    def __fspath__(self):
        return self.value


if __name__ == "__main__":
    unittest.main()