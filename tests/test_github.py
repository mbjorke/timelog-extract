"""Tests for GitHub collector helpers and public-events parsing."""

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from collectors import github as gh
from core.events import make_event as core_make_event


class GithubCollectorTests(unittest.TestCase):
    def test_resolve_github_user_prefers_cli(self):
        class Args:
            github_user = "cliuser"

        self.assertEqual(gh.resolve_github_username(Args()), "cliuser")
        self.assertEqual(gh.resolve_github_usernames(Args()), ["cliuser"])

    def test_resolve_github_usernames_comma_separated(self):
        class Args:
            github_user = "a, b"

        self.assertEqual(gh.resolve_github_usernames(Args()), ["a", "b"])

    def test_resolve_github_usernames_from_env_comma(self):
        class Args:
            github_user = None

        with patch.dict("os.environ", {"GITHUB_USER": "x,y"}, clear=True):
            self.assertEqual(gh.resolve_github_usernames(Args()), ["x", "y"])

    def test_github_source_auto_no_user_disabled(self):
        class Args:
            github_source = "auto"
            github_user = None

        with patch.dict("os.environ", {}, clear=True):
            en, reason = gh.github_source_enabled(Args())
        self.assertFalse(en)
        self.assertIsNotNone(reason)

    def test_github_source_on_requires_user(self):
        class Args:
            github_source = "on"
            github_user = ""

        with patch.dict("os.environ", {}, clear=True):
            en, reason = gh.github_source_enabled(Args())
        self.assertFalse(en)
        self.assertIn("username", reason.lower())

    def test_detail_push_event(self):
        ev = {
            "type": "PushEvent",
            "repo": {"name": "o/r"},
            "payload": {"ref": "refs/heads/main", "size": 2, "commits": [{"a": 1}, {"b": 2}]},
        }
        self.assertIn("push", gh._detail_for_event(ev).lower())
        self.assertIn("o/r", gh._detail_for_event(ev))

    @patch("collectors.github.urlopen")
    def test_collect_public_events_filters_range(self, mock_urlopen):
        t0 = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 8, 14, 0, tzinfo=timezone.utc)
        payload = [
            {
                "id": "1",
                "type": "PushEvent",
                "created_at": "2026-04-08T13:00:00Z",
                "repo": {"name": "o/r"},
                "payload": {"ref": "refs/heads/main", "commits": [{}]},
            },
            {
                "id": "2",
                "type": "PushEvent",
                "created_at": "2026-04-01T13:00:00Z",
                "repo": {"name": "o/old"},
                "payload": {"ref": "refs/heads/main", "commits": [{}]},
            },
        ]
        inner = MagicMock()
        inner.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = inner
        mock_urlopen.return_value.__exit__.return_value = None

        profiles = [{"name": "P", "match_terms": ["r"]}]

        def classify_project(text, profs, fallback="Uncategorized"):
            for pr in profs:
                for term in pr.get("match_terms", []):
                    if term in text.lower():
                        return pr["name"]
            return fallback

        events = gh.collect_public_events(
            profiles,
            t0,
            t1,
            username="u",
            token=None,
            classify_project=lambda t, p: classify_project(t, p),
            make_event=lambda src, ts, d, proj: core_make_event(src, ts, d, proj, "Uncategorized"),
            api_base="https://api.github.com",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "GitHub")
        self.assertEqual(events[0].get("_github_event_id"), "1")
        called_url = mock_urlopen.call_args[0][0].full_url
        self.assertIn("api.github.com/users/u/events/public", called_url)

    @patch("collectors.github.urlopen")
    def test_collect_public_events_custom_api_base(self, mock_urlopen):
        t0 = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 8, 14, 0, tzinfo=timezone.utc)
        payload = [
            {
                "id": "99",
                "type": "WatchEvent",
                "created_at": "2026-04-08T13:00:00Z",
                "repo": {"name": "o/r"},
                "payload": {},
            },
        ]
        inner = MagicMock()
        inner.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = inner
        mock_urlopen.return_value.__exit__.return_value = None

        profiles = [{"name": "P", "match_terms": ["r"]}]
        events = gh.collect_public_events(
            profiles,
            t0,
            t1,
            username="u",
            token=None,
            classify_project=lambda t, p: "P",
            make_event=lambda src, ts, d, proj: core_make_event(src, ts, d, proj, "Uncategorized"),
            api_base="https://git.example.com/api/v3",
        )
        self.assertEqual(len(events), 1)
        called_url = mock_urlopen.call_args[0][0].full_url
        self.assertTrue(
            called_url.startswith("https://git.example.com/api/v3/users/u/events/public"),
            called_url,
        )

    def test_merge_github_public_events_dedupes_by_id(self):
        ts = datetime(2026, 4, 8, 13, 0, tzinfo=timezone.utc)
        a = core_make_event("GitHub", ts, "detail", "P", "U")
        a["_github_event_id"] = "dup"
        b = core_make_event("GitHub", ts, "detail", "P", "U")
        b["_github_event_id"] = "dup"
        merged = gh.merge_github_public_events([[a], [b]])
        self.assertEqual(len(merged), 1)
        self.assertNotIn("_github_event_id", merged[0])

    def test_resolve_github_api_base_from_env(self):
        with patch.dict(os.environ, {"GITHUB_API_BASE_URL": "https://corp.github/api/v3/"}, clear=False):
            self.assertEqual(gh.resolve_github_api_base(), "https://corp.github/api/v3")


if __name__ == "__main__":
    unittest.main()
