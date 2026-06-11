"""Tests for mapping suggestion helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.mapping_suggestions import (
    github_slugs_in_text,
    profile_for_github_slug,
    suggest_project_for_signal,
    suggest_project_from_label_workspace,
    suggest_project_from_nearby_github,
)


class MappingSuggestionsTests(unittest.TestCase):
    def test_github_slugs_in_text(self):
        slugs = github_slugs_in_text("Pull requests · mbjorke/timelog-extract")
        self.assertIn("mbjorke/timelog-extract", slugs)

    def test_profile_for_github_slug_matches_project_name(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        self.assertEqual(profile_for_github_slug("mbjorke/timelog-extract", profiles), "timelog-extract")

    def test_lovable_signal_suggests_nearby_github_project(self):
        base = datetime(2026, 6, 11, 13, 0, tzinfo=timezone.utc)
        signal = {
            "kind": "host",
            "value": "810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com",
        }
        events = [
            {
                "source": "Lovable (desktop)",
                "local_ts": base,
                "detail": "storage signal — https://810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com/",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "local_ts": base.replace(minute=5),
                "detail": "Pull requests · mbjorke/timelog-extract",
                "project": "timelog-extract",
            },
        ]
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        self.assertEqual(
            suggest_project_from_nearby_github(signal, events, profiles),
            "timelog-extract",
        )

    def test_label_signal_suggests_workspace_dir(self):
        signal = {"kind": "label", "value": "uncommitted changes discussion"}
        events = [
            {
                "source": "Cursor",
                "detail": "Uncommitted changes discussion",
                "anchors": {"label": "uncommitted changes discussion", "dir": "akturo"},
                "project": "akturo",
            }
        ]
        profiles = [{"name": "akturo", "match_terms": ["akturo"]}]
        self.assertEqual(
            suggest_project_from_label_workspace(signal, events, profiles),
            "akturo",
        )

    def test_lovable_host_suggests_financing_portal_not_dev_alias(self):
        base = datetime(2026, 6, 11, 13, 0, tzinfo=timezone.utc)
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal", "ax-finans/financing-portal-dev"],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal-dev"],
            },
        ]
        events = [
            {
                "source": "Lovable (desktop)",
                "local_ts": base,
                "detail": "storage signal — https://810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com/",
                "project": "Uncategorized",
            },
            {
                "source": "GitHub",
                "local_ts": base.replace(minute=10),
                "detail": "PR #9 merged (ax-finans/financing-portal)",
                "project": "financing-portal",
            },
            {
                "source": "Chrome",
                "local_ts": base.replace(minute=12),
                "detail": "Pull requests · ax-finans/financing-portal-dev-31e799cf",
                "project": "Uncategorized",
            },
        ]
        signal = {
            "kind": "host",
            "value": "810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com",
        }
        self.assertEqual(
            suggest_project_for_signal(signal, profiles=profiles, events=events),
            "financing-portal",
        )


if __name__ == "__main__":
    unittest.main()
