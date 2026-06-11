"""Tests for gh CLI repo discovery."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.gh_repo_discovery import (
    _GH_ROWS_CACHE,
    collect_gh_repo_list_data,
    collect_gh_repos_created_in_window,
    github_owners_for_repo_discovery,
)


class GhRepoDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        _GH_ROWS_CACHE.clear()

    def test_github_owners_ignores_tracked_url_hosts(self):
        profiles = [
            {
                "name": "demo",
                "match_terms": ["mbjorke/timelog-extract"],
                "tracked_urls": ["https://facebook.com/groups/example"],
            },
        ]
        owners = github_owners_for_repo_discovery(profiles)
        self.assertIn("mbjorke", owners)
        self.assertNotIn("facebook.com", owners)

    def test_returns_repos_created_in_window_for_known_owner(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        dt_from = datetime(2026, 6, 10, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 12, tzinfo=timezone.utc)
        payload = [
            {
                "nameWithOwner": "mbjorke/landsbanken-faq-helper",
                "createdAt": "2026-06-11T10:15:00Z",
                "pushedAt": "2026-06-11T12:00:00Z",
            },
            {
                "nameWithOwner": "mbjorke/old-repo",
                "createdAt": "2025-01-01T00:00:00Z",
                "pushedAt": "2025-06-01T00:00:00Z",
            },
        ]
        gh_status = type("S", (), {"authenticated": True, "login": "mbjorke"})()

        def fake_run(cmd, **_kwargs):
            if "repo" in cmd and "list" in cmd:
                return type("R", (), {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""})()
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "fail"})()

        with patch("core.gh_repo_discovery.probe_gh_cli_auth", return_value=gh_status), patch(
            "core.gh_repo_discovery.shutil.which", return_value="/usr/bin/gh"
        ), patch("core.gh_repo_discovery.subprocess.run", side_effect=fake_run):
            found = collect_gh_repos_created_in_window(dt_from, dt_to, profiles=profiles)

        self.assertEqual(list(found), ["mbjorke/landsbanken-faq-helper"])
        self.assertTrue(found["mbjorke/landsbanken-faq-helper"].startswith("2026-06-11"))

    def test_collect_list_data_includes_pushed_epochs(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        dt_from = datetime(2026, 6, 10, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 12, tzinfo=timezone.utc)
        payload = [
            {
                "nameWithOwner": "mbjorke/landsbanken-faq-helper",
                "createdAt": "2026-06-11T10:15:00Z",
                "pushedAt": "2026-06-11T12:00:00Z",
            },
        ]
        gh_status = type("S", (), {"authenticated": True, "login": "mbjorke"})()

        def fake_run(cmd, **_kwargs):
            return type("R", (), {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""})()

        with patch("core.gh_repo_discovery.probe_gh_cli_auth", return_value=gh_status), patch(
            "core.gh_repo_discovery.shutil.which", return_value="/usr/bin/gh"
        ), patch("core.gh_repo_discovery.subprocess.run", side_effect=fake_run):
            created, pushed = collect_gh_repo_list_data(dt_from, dt_to, profiles=profiles)

        self.assertIn("mbjorke/landsbanken-faq-helper", created)
        self.assertGreater(pushed["mbjorke/landsbanken-faq-helper"], 0)

    def test_skips_when_gh_not_authenticated(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        dt_from = datetime(2026, 6, 10, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 12, tzinfo=timezone.utc)
        gh_status = type("S", (), {"authenticated": False, "login": ""})()
        with patch("core.gh_repo_discovery.probe_gh_cli_auth", return_value=gh_status):
            found = collect_gh_repos_created_in_window(dt_from, dt_to, profiles=profiles)
        self.assertEqual(found, {})

    def test_skips_unknown_owners(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        dt_from = datetime(2026, 6, 10, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 12, tzinfo=timezone.utc)
        payload = [{"nameWithOwner": "other-org/secret-repo", "createdAt": "2026-06-11T10:00:00Z"}]
        gh_status = type("S", (), {"authenticated": True, "login": "mbjorke"})()

        def fake_run(cmd, **_kwargs):
            return type("R", (), {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""})()

        with patch("core.gh_repo_discovery.probe_gh_cli_auth", return_value=gh_status), patch(
            "core.gh_repo_discovery.shutil.which", return_value="/usr/bin/gh"
        ), patch("core.gh_repo_discovery.subprocess.run", side_effect=fake_run):
            found = collect_gh_repos_created_in_window(dt_from, dt_to, profiles=profiles)
        self.assertEqual(found, {})


if __name__ == "__main__":
    unittest.main()
