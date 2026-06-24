"""Tests for live Jira credential verification (used by onboarding)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import collectors.jira as jira_mod
from collectors.jira import JiraCredentials, verify_jira_credentials

TEST_API_PLACEHOLDER = "fake-token"


class JiraVerifyTests(unittest.TestCase):
    def _creds(self):
        return JiraCredentials(
            base_url="https://example.atlassian.net", email="e@x.com", api_token=TEST_API_PLACEHOLDER
        )

    def test_verify_ok_names_account(self):
        import json as _json

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return _json.dumps({"emailAddress": "marcus@x.se"}).encode()

        with patch.object(jira_mod, "urlopen", return_value=_Resp()):
            ok, detail, suspect = verify_jira_credentials(self._creds())
        self.assertTrue(ok)
        self.assertIn("marcus@x.se", detail)
        self.assertEqual(suspect, "")

    def test_verify_http_401_flags_credentials(self):
        from urllib.error import HTTPError

        err = HTTPError("https://example.atlassian.net/rest/api/3/myself", 401, "Unauthorized", {}, None)
        with patch.object(jira_mod, "urlopen", side_effect=err):
            ok, detail, suspect = verify_jira_credentials(self._creds())
        self.assertFalse(ok)
        self.assertEqual(suspect, "credentials")

    def test_verify_bad_base_url_flags_url(self):
        creds = JiraCredentials(base_url="not-a-url", email="e@x.com", api_token=TEST_API_PLACEHOLDER)
        ok, _detail, suspect = verify_jira_credentials(creds)
        self.assertFalse(ok)
        self.assertEqual(suspect, "url")

    def test_verify_rejects_plain_http(self):
        creds = JiraCredentials(
            base_url="http://insecure.example.com", email="e@x.com", api_token=TEST_API_PLACEHOLDER
        )
        ok, detail, suspect = verify_jira_credentials(creds)
        self.assertFalse(ok)
        self.assertEqual(suspect, "url")
        self.assertIn("https", detail)


if __name__ == "__main__":
    unittest.main()
