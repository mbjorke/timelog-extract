"""Tests for GitHub collector helpers and public-events parsing."""

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import MagicMock, patch

from collectors import github as gh
from core.events import make_event as core_make_event


class GithubCollectorTests(unittest.TestCase):
    def test_resolve_github_user_prefers_cli(self):
        class Args:
            github_user = "cliuser"

        self.assertEqual(gh.resolve_github_username(Args()), "cliuser")

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
                "type": "PushEvent",
                "created_at": "2026-04-08T13:00:00Z",
                "repo": {"name": "o/r"},
                "payload": {"ref": "refs/heads/main", "commits": [{}]},
            },
            {
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
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "GitHub")


if __name__ == "__main__":
    unittest.main()
