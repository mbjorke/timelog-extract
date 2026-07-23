"""HTTPS and redirect security tests for the Jira collector client."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

from collectors.jira import (
    JiraCredentials,
    _RejectHttpRedirectHandler,
    list_jira_worklogs,
    post_jira_worklog,
    verify_jira_credentials,
)

TEST_API_PLACEHOLDER = "fake-token"


class JiraHttpsSecurityTests(unittest.TestCase):
    def test_list_jira_worklogs_rejects_insecure_http(self):
        creds = JiraCredentials("http://insecure.example.com", "fake@example.com", TEST_API_PLACEHOLDER)
        with patch("collectors.jira.urlopen") as mock_urlopen:
            with self.assertRaises(ValueError) as ctx:
                list_jira_worklogs(creds, "ABC-1")
            mock_urlopen.assert_not_called()
        self.assertIn("HTTPS", str(ctx.exception))

    def test_post_jira_worklog_rejects_insecure_http(self):
        creds = JiraCredentials("http://insecure.example.com", "fake@example.com", TEST_API_PLACEHOLDER)
        with patch("collectors.jira.urlopen") as mock_urlopen:
            with self.assertRaises(ValueError) as ctx:
                post_jira_worklog(
                    creds,
                    "ABC-1",
                    datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
                    3600,
                    "sync test",
                )
            mock_urlopen.assert_not_called()
        self.assertIn("HTTPS", str(ctx.exception))

    def test_jira_rejects_https_to_http_redirect_without_sending_credentials(self):
        creds = JiraCredentials(
            base_url="https://example.atlassian.net",
            email="fake@example.com",
            api_token=TEST_API_PLACEHOLDER,
        )
        handler = _RejectHttpRedirectHandler()
        req = Request(f"{creds.base_url}/rest/api/3/myself")
        req.add_header("Authorization", "Basic secret-token")
        with self.assertRaises(URLError) as ctx:
            handler.redirect_request(
                req,
                None,
                302,
                "Found",
                {},
                "http://insecure.example.com/rest/api/3/myself",
            )
        self.assertIn("http", str(ctx.exception.reason).lower())

        with patch("collectors.jira.urlopen", side_effect=URLError(str(ctx.exception.reason))) as mock_urlopen:
            ok, detail, suspect = verify_jira_credentials(creds)
        self.assertFalse(ok)
        self.assertEqual(suspect, "url")
        mock_urlopen.assert_called_once()
        self.assertTrue(mock_urlopen.call_args[0][0].full_url.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
