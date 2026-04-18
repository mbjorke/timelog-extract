"""Tests for Jira-related PR changes (collectors/jira.py and core/jira_sync.py).

Kept separate from test_jira_sync.py because that file imports ReportPayload
which transitively requires typer (not available in this test environment).
These tests only depend on collectors.jira and core.jira_sync directly.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class JiraCollectorUrlEncodingTests(unittest.TestCase):
    """Tests for quote(issue_key) URL-encoding added in collectors/jira.py in this PR."""

    def _fake_urlopen(self, captured_urls: list, response_body: bytes = b'{"id": "99"}'):
        """Return a fake urlopen that records the request URL."""
        def fake_urlopen(req, timeout=20):
            captured_urls.append(req.full_url)
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = response_body
            return mock_resp
        return fake_urlopen

    def test_issue_key_with_slash_is_percent_encoded_in_url(self):
        """Slashes in issue keys must be percent-encoded so they don't split the URL path."""
        from collectors.jira import JiraCredentials, post_jira_worklog

        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="user@example.com",
            api_token="tok",
        )
        started = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        captured: list[str] = []

        with patch("collectors.jira.urlopen", self._fake_urlopen(captured)):
            post_jira_worklog(
                creds=creds,
                issue_key="PROJ/123",
                started=started,
                time_spent_seconds=3600,
                comment="test",
            )

        self.assertEqual(len(captured), 1)
        self.assertIn("PROJ%2F123", captured[0])
        self.assertNotIn("PROJ/123/worklog", captured[0])

    def test_normal_issue_key_appears_verbatim_in_url(self):
        """Standard issue keys (e.g. ABC-123) contain only safe chars and must not be mangled."""
        from collectors.jira import JiraCredentials, post_jira_worklog

        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="user@example.com",
            api_token="tok",
        )
        started = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        captured: list[str] = []

        with patch("collectors.jira.urlopen", self._fake_urlopen(captured, b'{"id": "42"}')):
            worklog_id = post_jira_worklog(
                creds=creds,
                issue_key="ABC-123",
                started=started,
                time_spent_seconds=1800,
                comment="normal",
            )

        self.assertEqual(worklog_id, "42")
        self.assertIn("ABC-123/worklog", captured[0])

    def test_issue_key_with_space_is_percent_encoded(self):
        """Spaces (unusual but possible in some Jira configs) must be percent-encoded."""
        from collectors.jira import JiraCredentials, post_jira_worklog

        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="user@example.com",
            api_token="tok",
        )
        started = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        captured: list[str] = []

        with patch("collectors.jira.urlopen", self._fake_urlopen(captured)):
            post_jira_worklog(
                creds=creds,
                issue_key="PROJ 123",
                started=started,
                time_spent_seconds=3600,
                comment="space test",
            )

        self.assertEqual(len(captured), 1)
        # Space should be encoded as %20
        self.assertIn("PROJ%20123", captured[0])

    def test_url_ends_with_worklog_segment(self):
        """The URL path must always end with /worklog after the encoded issue key."""
        from collectors.jira import JiraCredentials, post_jira_worklog

        creds = JiraCredentials(
            base_url="https://jira.example.com",
            email="a@b.com",
            api_token="x",
        )
        started = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        captured: list[str] = []

        with patch("collectors.jira.urlopen", self._fake_urlopen(captured)):
            post_jira_worklog(
                creds=creds,
                issue_key="XY-99",
                started=started,
                time_spent_seconds=3600,
                comment="c",
            )

        self.assertTrue(captured[0].endswith("/worklog"), f"URL did not end with /worklog: {captured[0]}")


class GitCommitFieldRenameTests(unittest.TestCase):
    """Tests for GitCommit.authored_at -> committed_at rename in core/jira_sync.py (PR change)."""

    def test_git_commit_accepts_committed_at_keyword(self):
        """GitCommit dataclass must accept committed_at as a keyword argument."""
        from core.jira_sync import GitCommit

        ts = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        commit = GitCommit(committed_at=ts, subject="ABC-1 test commit")
        self.assertEqual(commit.committed_at, ts)
        self.assertEqual(commit.subject, "ABC-1 test commit")

    def test_git_commit_field_is_committed_at_not_authored_at(self):
        """The renamed field must be accessible as committed_at."""
        from core.jira_sync import GitCommit
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(GitCommit)}
        self.assertIn("committed_at", field_names)
        self.assertNotIn("authored_at", field_names)

    def test_git_commit_authored_at_raises_type_error(self):
        """Constructing GitCommit with authored_at keyword must raise TypeError."""
        from core.jira_sync import GitCommit

        ts = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        with self.assertRaises(TypeError):
            GitCommit(authored_at=ts, subject="bad field name")  # type: ignore[call-arg]

    def test_issue_key_resolution_uses_committed_at(self):
        """_issue_key_for_session must compare against committed_at (regression guard)."""
        from types import SimpleNamespace
        from core.jira_sync import _issue_key_for_session

        start = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        mid = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)

        commits = [SimpleNamespace(committed_at=mid, subject="XYZ-42 implement feature")]
        key, source = _issue_key_for_session(start, end, commits, branch_key=None)
        self.assertEqual(key, "XYZ-42")
        self.assertEqual(source, "commit")


if __name__ == "__main__":
    unittest.main()