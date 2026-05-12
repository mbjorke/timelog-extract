from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from core.cli_triage_map_candidates import UrlCandidate, _auto_assign_high, _confidence_rank, build_url_candidates, build_url_candidates_from_gap_days


class TriageMapTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_build_url_candidates_prefers_title_and_url_key(self):
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Chrome",
                    "timestamp": datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
                    "detail": "PR review — https://github.com/org/repo/pull/123",
                    "project": "Uncategorized",
                },
                {
                    "source": "Chrome",
                    "timestamp": datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
                    "detail": "Issue — https://github.com/org/repo/issues/5",
                    "project": "Uncategorized",
                },
            ]
        )
        profiles = [{"name": "timelog-extract", "match_terms": ["org/repo"], "tracked_urls": [], "enabled": True}]
        rows = build_url_candidates(report=report, profiles=profiles, max_rows=10, min_events=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url_key, "github.com/org/repo")
        self.assertIn(rows[0].title, {"PR review", "Issue"})

    def test_build_url_candidates_ignores_non_web_and_noise_hosts(self):
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Cursor",
                    "timestamp": datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
                    "detail": "Please fetch https://noise-app.example.invalid",
                    "project": "Uncategorized",
                },
                {
                    "source": "Chrome",
                    "timestamp": datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
                    "detail": "storage signal — https://00000000-0000-4000-8000-000000000001.lovableproject.com",
                    "project": "Uncategorized",
                },
                {
                    "source": "Chrome",
                    "timestamp": datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
                    "detail": "Repo — https://github.com/org/repo/issues/1",
                    "project": "Uncategorized",
                },
                {
                    "source": "Chrome",
                    "timestamp": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                    "detail": "Repo — https://github.com/org/repo/pull/2",
                    "project": "Uncategorized",
                },
            ]
        )
        rows = build_url_candidates(report=report, profiles=[], max_rows=10, min_events=2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url_key, "github.com/org/repo")

    def test_build_url_candidates_include_low_signal_keeps_noise_rows(self):
        report = SimpleNamespace(
            included_events=[
                {
                    "source": "Lovable (desktop)",
                    "timestamp": datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc),
                    "detail": "storage signal — https://00000000-0000-4000-8000-000000000001.lovableproject.com",
                    "project": "Uncategorized",
                }
            ]
        )
        rows = build_url_candidates(report=report, profiles=[], max_rows=10, min_events=2, include_low_signal=True)
        self.assertEqual(len(rows), 1)

    def test_cli_triage_map_no_candidates_exits_cleanly(self):
        plan = {"days": [{"day": "2026-04-11"}]}
        with patch("core.cli_triage_map.build_triage_plan_dict", return_value=plan), patch(
            "core.cli_triage_map.build_url_candidates_from_gap_days", return_value=[]
        ), patch("core.cli_triage_map.load_triage_profiles", return_value=[]):
            result = self.runner.invoke(
                app,
                ["triage-map", "--today", "--projects-config", os.path.join(tempfile.gettempdir(), "gittan-triage-map-missing.json")],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("No URL candidates found", result.output)

    def test_confidence_rank_orders_high_before_medium_before_low(self):
        rows = [
            UrlCandidate("a", "k1", "P", "low", 0.1, 0.2, 10, 1, "2026-01-01", []),
            UrlCandidate("b", "k2", "P", "high", 0.9, 1.7, 2, 1, "2026-01-01", []),
            UrlCandidate("c", "k3", "P", "medium", 0.6, 0.8, 5, 1, "2026-01-01", []),
        ]
        rows.sort(key=lambda row: (_confidence_rank(row.confidence_label), -row.confidence_score, -row.events, row.url_key))
        self.assertEqual([r.confidence_label for r in rows], ["high", "medium", "low"])

    def test_auto_assign_high_selects_only_valid_high_rows(self):
        rows = [
            UrlCandidate("a", "k1", "P1", "high", 1.0, 2.0, 10, 1, "2026-01-01", []),
            UrlCandidate("b", "k2", "Uncategorized", "high", 1.0, 1.0, 10, 1, "2026-01-01", []),
            UrlCandidate("c", "k3", "P2", "medium", 0.7, 0.5, 10, 1, "2026-01-01", []),
        ]
        assigned = _auto_assign_high(rows, ["P1", "P2"])
        self.assertEqual(assigned, {"k1": "P1"})

    def test_gap_day_impact_is_counted_once_per_key_and_day(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["org/repo"], "tracked_urls": [], "enabled": True}]
        with patch("core.cli_triage_map_candidates.fetch_chrome_rows_for_day") as fetch_mock, patch(
            "core.cli_triage_map_candidates._filter_triage_noise_rows"
        ) as filter_mock:
            fetch_mock.return_value = [
                (1, "https://github.com/org/repo/pull/1", "PR 1"),
                (2, "https://github.com/org/repo/pull/2", "PR 2"),
            ]
            filter_mock.return_value = (fetch_mock.return_value, 0)
            rows = build_url_candidates_from_gap_days(
                day_unexplained_hours={"2026-04-11": 4.0},
                profiles=profiles,
                max_rows=10,
                min_events=1,
            )
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].impact_hours, 4.0, places=6)


if __name__ == "__main__":
    unittest.main()
