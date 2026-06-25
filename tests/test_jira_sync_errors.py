"""CLI error-handling for jira-sync: a 404 issue skips, a network error aborts."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from collectors.jira import JiraApiError, JiraCredentials
from core.cli import app
from core.jira_sync import JiraWorklogCandidate

TEST_API_PLACEHOLDER = "fake-token"


def _creds():
    return JiraCredentials(
        base_url="https://example.atlassian.net",
        email="fake@example.com",
        api_token=TEST_API_PLACEHOLDER,
    )


def _candidate(issue_key: str, hour: int = 10) -> JiraWorklogCandidate:
    return JiraWorklogCandidate(
        issue_key=issue_key,
        day="2026-04-20",
        started=datetime(2026, 4, 20, hour, 0, tzinfo=timezone.utc),
        seconds=3600,
        projects=["Demo"],
        source="commit",
    )


class JiraSyncErrorHandlingTests(unittest.TestCase):
    def test_404_issue_is_skipped_and_run_continues(self):
        runner = CliRunner()
        valid = _candidate("KAN-1", hour=10)
        ghkey = _candidate("GH-143", hour=9)

        def fake_list(_creds, key):
            if key == "GH-143":
                raise JiraApiError("Jira HTTP 404: issue does not exist", status=404)
            return []

        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=_creds()), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates", return_value=([valid, ghkey], 0)
        ), patch(
            "core.cli_jira_sync.list_jira_worklogs", side_effect=fake_list
        ), patch("core.cli_jira_sync.typer.confirm", return_value=True), patch(
            "core.cli_jira_sync.post_candidate", return_value="10001"
        ):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Skipped GH-143", result.output)
        self.assertIn("not_found=1", result.output)
        self.assertIn("posted=1", result.output)

    def test_network_error_still_fails_closed(self):
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=_creds()), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates", return_value=([_candidate("ABC-1")], 0)
        ), patch(
            "core.cli_jira_sync.list_jira_worklogs",
            side_effect=JiraApiError("Jira network error", status=None),
        ), patch("core.cli_jira_sync.post_candidate") as post:
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        post.assert_not_called()
        self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
