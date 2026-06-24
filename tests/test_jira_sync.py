"""Tests for Jira sync key resolution and aggregation."""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from collectors.jira import JiraCredentials, adf_comment_text, post_jira_worklog
from core.cli import app
from core.cli_jira_sync import _next_step_hint
from core.jira_sync import (
    JiraWorklogCandidate,
    JiraSyncSummary,
    build_jira_worklog_candidates,
    candidate_already_posted,
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
        self.assertIn("Jira sync summary: posted=0, already=0, skipped=2, unresolved=0, failed=0", result.output)
        self.assertIn("Next: rerun with confirmation", result.output)

    def test_cli_jira_sync_no_candidates_no_unresolved_shows_hint(self):
        runner = CliRunner()
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
            return_value=([], 0),
        ):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on", "--dry-run"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("No Jira worklog candidates found.", result.output)
        self.assertIn("widen the date range", result.output)

    def test_cli_jira_sync_success_posts_next_step_hint(self):
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
            "core.cli_jira_sync.list_jira_worklogs", return_value=[]
        ), patch("core.cli_jira_sync.post_candidate", return_value="10001"):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Jira sync summary: posted=1, already=0, skipped=0, unresolved=0, failed=0", result.output)
        self.assertIn("Next: verify worklogs in Jira for the posted issue(s).", result.output)

    def test_list_jira_worklogs_follows_pagination(self):
        import json as _json

        from collectors.jira import list_jira_worklogs

        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        pages = [
            _json.dumps({"startAt": 0, "maxResults": 2, "total": 3, "worklogs": [{"id": "1"}, {"id": "2"}]}).encode(),
            _json.dumps({"startAt": 2, "maxResults": 2, "total": 3, "worklogs": [{"id": "3"}]}).encode(),
        ]

        class _FakeResp:
            def __init__(self, data):
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.data

        calls = []

        def _fake_urlopen(req, timeout=None):
            calls.append(req.full_url)
            return _FakeResp(pages[len(calls) - 1])

        with patch("collectors.jira.urlopen", side_effect=_fake_urlopen):
            result = list_jira_worklogs(creds, "KAN-1")
        self.assertEqual([w["id"] for w in result], ["1", "2", "3"])
        self.assertEqual(len(calls), 2)
        self.assertIn("startAt=2", calls[1])

    def test_cli_jira_sync_aborts_when_worklog_list_fails(self):
        runner = CliRunner()
        candidate = JiraWorklogCandidate(
            issue_key="ABC-1",
            day="2026-04-20",
            started=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            seconds=7200,
            projects=["Demo"],
            source="commit",
        )
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        with patch("core.report_service.run_timelog_report", return_value=SimpleNamespace()), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=creds), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates", return_value=([candidate], 0)
        ), patch(
            "core.cli_jira_sync.list_jira_worklogs", side_effect=RuntimeError("Jira down")
        ), patch("core.cli_jira_sync.post_candidate") as post:
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        # Fail closed: no post attempted, non-zero exit.
        post.assert_not_called()
        self.assertNotEqual(result.exit_code, 0)

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
            "core.cli_jira_sync.list_jira_worklogs", return_value=[]
        ), patch("core.cli_jira_sync.post_candidate", side_effect=RuntimeError("Jira HTTP 404")):
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Jira sync summary: posted=0, already=0, skipped=0, unresolved=0, failed=1", result.output)
        self.assertIn("Next: verify Jira credentials and issue visibility", result.output)


def _adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _candidate() -> JiraWorklogCandidate:
    return JiraWorklogCandidate(
        issue_key="KAN-1",
        day="2026-06-18",
        started=datetime(2026, 6, 18, 14, 9, 49, tzinfo=timezone.utc),
        seconds=3600,
        projects=["Demo"],
        source="branch",
    )


class JiraDedupTests(unittest.TestCase):
    def test_marker_is_embedded_in_comment(self):
        candidate = _candidate()
        self.assertEqual(candidate.marker, "[gittan:KAN-1:2026-06-18]")
        self.assertIn(candidate.marker, candidate.comment)

    def test_adf_comment_text_handles_shapes(self):
        self.assertEqual(adf_comment_text(None), "")
        self.assertEqual(adf_comment_text("plain string [gittan:KAN-1:2026-06-18]"),
                         "plain string [gittan:KAN-1:2026-06-18]")
        self.assertIn("hello", adf_comment_text(_adf("hello world")))
        # Defensive: unexpected shapes never raise.
        self.assertEqual(adf_comment_text(12345), "")
        self.assertEqual(adf_comment_text({"type": "doc"}), "")

    def test_candidate_already_posted_detects_marker(self):
        candidate = _candidate()
        existing = [{"comment": _adf(f"Gittan sync (2026-06-18) project(s): Demo {candidate.marker}")}]
        self.assertTrue(candidate_already_posted(candidate, existing))

    def test_candidate_not_posted_when_no_marker(self):
        candidate = _candidate()
        existing = [
            {"comment": _adf("some unrelated manual worklog")},
            {"comment": None},
            {"comment": "string with [gittan:OTHER-9:2026-06-18]"},
            "garbage-not-a-dict",
        ]
        self.assertFalse(candidate_already_posted(candidate, existing))

    def test_cli_skips_existing_marker(self):
        runner = CliRunner()
        candidate = _candidate()
        fake_report = SimpleNamespace()
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        existing = [{"comment": _adf(f"Gittan sync ({candidate.day}) project(s): Demo {candidate.marker}")}]
        with patch("core.report_service.run_timelog_report", return_value=fake_report), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=creds), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates", return_value=([candidate], 0)
        ), patch("core.cli_jira_sync.typer.confirm", return_value=True), patch(
            "core.cli_jira_sync.list_jira_worklogs", return_value=existing
        ), patch("core.cli_jira_sync.post_candidate", return_value="10001") as post_mock:
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        post_mock.assert_not_called()
        self.assertIn("Already synced KAN-1", result.output)
        self.assertIn("Jira sync summary: posted=0, already=1, skipped=0, unresolved=0, failed=0", result.output)
        self.assertIn("already synced", result.output)

    def test_cli_posts_when_no_existing_marker(self):
        runner = CliRunner()
        candidate = _candidate()
        fake_report = SimpleNamespace()
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        with patch("core.report_service.run_timelog_report", return_value=fake_report), patch(
            "core.cli_jira_sync.jira_sync_enabled", return_value=(True, "")
        ), patch("core.cli_jira_sync.resolve_jira_credentials", return_value=creds), patch(
            "core.cli_jira_sync.build_jira_worklog_candidates", return_value=([candidate], 0)
        ), patch("core.cli_jira_sync.typer.confirm", return_value=True), patch(
            "core.cli_jira_sync.list_jira_worklogs", return_value=[{"comment": _adf("unrelated")}]
        ), patch("core.cli_jira_sync.post_candidate", return_value="10001") as post_mock:
            result = runner.invoke(app, ["jira-sync", "--today", "--jira-sync", "on"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        post_mock.assert_called_once()
        self.assertIn("Jira sync summary: posted=1, already=0, skipped=0, unresolved=0, failed=0", result.output)


class NextStepHintTests(unittest.TestCase):
    """Unit tests for _next_step_hint (always returns a single concise str — see PR #85)."""

    def test_hint_when_all_zero(self):
        summary = JiraSyncSummary(posted=0, skipped=0, unresolved=0, failed=0)
        self.assertIn("nothing to post", _next_step_hint(summary))

    def test_hint_when_only_posted(self):
        summary = JiraSyncSummary(posted=3, skipped=0, unresolved=0, failed=0)
        self.assertIn("verify worklogs in Jira", _next_step_hint(summary))

    def test_hint_for_failed(self):
        summary = JiraSyncSummary(posted=0, skipped=0, unresolved=0, failed=1)
        hint = _next_step_hint(summary)
        self.assertIsNotNone(hint)
        self.assertIn("credentials", hint)

    def test_hint_for_unresolved(self):
        summary = JiraSyncSummary(posted=0, skipped=0, unresolved=2, failed=0)
        hint = _next_step_hint(summary)
        self.assertIsNotNone(hint)
        self.assertIn("issue keys", hint)

    def test_hint_for_skipped(self):
        summary = JiraSyncSummary(posted=0, skipped=1, unresolved=0, failed=0)
        hint = _next_step_hint(summary)
        self.assertIsNotNone(hint)
        self.assertIn("rerun with confirmation", hint)

    def test_hint_for_already(self):
        summary = JiraSyncSummary(posted=0, already=2, skipped=0, unresolved=0, failed=0)
        hint = _next_step_hint(summary)
        self.assertIn("already synced", hint)

    def test_hint_already_takes_priority_over_skipped(self):
        summary = JiraSyncSummary(posted=0, already=1, skipped=1, unresolved=0, failed=0)
        hint = _next_step_hint(summary)
        self.assertIn("already synced", hint)

    def test_hint_failed_takes_priority_over_unresolved(self):
        """Failed check happens before unresolved check."""
        summary = JiraSyncSummary(posted=0, skipped=0, unresolved=1, failed=1)
        hint = _next_step_hint(summary)
        self.assertIsNotNone(hint)
        self.assertIn("credentials", hint)

    def test_hint_unresolved_takes_priority_over_skipped(self):
        """Unresolved check happens before skipped check."""
        summary = JiraSyncSummary(posted=0, skipped=1, unresolved=1, failed=0)
        hint = _next_step_hint(summary)
        self.assertIsNotNone(hint)
        self.assertIn("issue keys", hint)


class PathLike:
    def __init__(self, value: str):
        self.value = value

    def __fspath__(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
