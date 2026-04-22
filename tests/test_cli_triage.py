from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.cli_triage import (
    AGENT_TRIAGE_SCHEMA_VERSION,
    _build_site_time_hints,
    build_triage_plan_dict,
    resolve_target_project_name,
    select_triage_days,
)


class CliTriageHelpersTests(unittest.TestCase):
    def test_build_site_time_hints_adds_first_last_and_sample_window(self):
        rows = [
            (132_537_602_000_000, "https://github.com/mbjorke/timelog-extract", "A"),
            (132_537_605_000_000, "https://www.github.com/mbjorke/timelog-extract/pulls", "B"),
        ]
        hints = _build_site_time_hints(rows)
        self.assertIn("github.com", hints)
        gh = hints["github.com"]
        self.assertIn("first_seen_local", gh)
        self.assertIn("last_seen_local", gh)
        self.assertIn("sample_window_local", gh)
        self.assertIn("start", gh["sample_window_local"])
        self.assertIn("end", gh["sample_window_local"])

    def test_select_triage_days_sorts_by_unexplained_desc(self):
        payload = {
            "days": [
                {"day": "2026-04-01", "unexplained_screen_time_hours": 1.0},
                {"day": "2026-04-02", "unexplained_screen_time_hours": 3.0},
                {"day": "2026-04-03", "unexplained_screen_time_hours": 0.0},
            ]
        }
        rows = select_triage_days(payload, max_days=2)
        self.assertEqual([row["day"] for row in rows], ["2026-04-02", "2026-04-01"])

    def test_resolve_target_project_name_prefers_exact_name(self):
        profiles = [
            {"name": "Project A", "canonical_project": "Suite"},
            {"name": "Project B", "canonical_project": "Suite"},
        ]
        self.assertEqual(resolve_target_project_name(profiles, "Project B"), "Project B")

    def test_resolve_target_project_name_falls_back_to_first_canonical_match(self):
        profiles = [
            {"name": "Project A", "canonical_project": "Suite"},
            {"name": "Project B", "canonical_project": "Suite"},
        ]
        self.assertEqual(resolve_target_project_name(profiles, "Suite"), "Project A")

    @patch("core.report_service.run_timelog_report")
    def test_build_triage_plan_dict_empty_when_no_unexplained_hours(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            project_reports={"P": {"2026-01-01": {"hours": 2.0}}},
            overall_days={"2026-01-01": {"hours": 2.0}},
            screen_time_days={"2026-01-01": 3600.0},
        )
        raw = '{"version": 1, "projects": [{"name": "Only", "canonical_project": "Only", "tracked_urls": [], "match_terms": []}]}'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        try:
            plan = build_triage_plan_dict(
                date_from=None,
                date_to=None,
                projects_config=path,
                max_days=3,
                max_sites=5,
                scoring_mode="site-first",
            )
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertEqual(plan["schema_version"], AGENT_TRIAGE_SCHEMA_VERSION)
        self.assertEqual(plan["empty_reason"], "no_unexplained_days")
        self.assertEqual(plan["days"], [])
        self.assertIn("notes_for_agents", plan)
        self.assertNotIn("sample_title", json.dumps(plan))

    @patch("core.report_service.run_timelog_report")
    def test_build_triage_plan_top_sites_include_timestamp_hints(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            dt_from=None,
            dt_to=None,
            args=SimpleNamespace(min_session=15, min_session_passive=5),
            overall_days={},
            project_reports={},
            screen_time_days={},
        )
        raw = (
            '{"version": 1, "projects": [{"name": "Only", "canonical_project": "Only", '
            '"tracked_urls": ["github.com"], "match_terms": []}]}'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        gap_payload = {
            "days": [
                {
                    "day": "2026-04-21",
                    "estimated_hours": 2.0,
                    "screen_time_hours": 2.5,
                    "unexplained_screen_time_hours": 1.2,
                }
            ]
        }
        chrome_rows = [
            (132_537_602_000_000, "https://github.com/mbjorke/timelog-extract", "repo"),
            (132_537_605_000_000, "https://github.com/mbjorke/timelog-extract/pulls", "pr"),
        ]
        try:
            with patch("core.cli_triage.analyze_screen_time_gaps", return_value=gap_payload), patch(
                "core.cli_triage.fetch_chrome_rows_for_day", return_value=chrome_rows
            ):
                plan = build_triage_plan_dict(
                    date_from=None,
                    date_to=None,
                    projects_config=path,
                    max_days=3,
                    max_sites=5,
                    scoring_mode="site-first",
                )
        finally:
            Path(path).unlink(missing_ok=True)
        top_sites = plan["days"][0]["top_sites"]
        self.assertGreaterEqual(len(top_sites), 1)
        first = top_sites[0]
        self.assertEqual(first["domain"], "github.com")
        self.assertIn("first_seen_local", first)
        self.assertIn("last_seen_local", first)
        self.assertIn("sample_window_local", first)
        self.assertIn("start", first["sample_window_local"])
        self.assertIn("end", first["sample_window_local"])

    def test_triage_json_and_yes_are_mutually_exclusive(self):
        repo = Path(__file__).resolve().parent.parent
        r = subprocess.run(
            [sys.executable, str(repo / "timelog_extract.py"), "triage", "--json", "--yes"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Cannot combine", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
