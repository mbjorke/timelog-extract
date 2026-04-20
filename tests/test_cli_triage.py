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
    build_triage_plan_dict,
    resolve_target_project_name,
    select_triage_days,
)


class CliTriageHelpersTests(unittest.TestCase):
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
