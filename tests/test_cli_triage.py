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
    _build_choices,
    _build_question,
    _filter_triage_noise_rows,
    _is_triage_noise_row,
    _suggestion_to_plan_dict,
    build_triage_plan_dict,
    load_triage_profiles,
    resolve_target_project_name,
    select_triage_days,
)
from scripts.calibration.gap_day_triage import ProjectSuggestion


class CliTriageHelpersTests(unittest.TestCase):
    def test_is_triage_noise_row_matches_known_cursor_noise(self):
        self.assertTrue(_is_triage_noise_row("https://cursor.com/changelog", "Cursor release notes"))
        self.assertTrue(
            _is_triage_noise_row("https://example.com", "Canvas SDK mirror failed in background")
        )
        self.assertFalse(_is_triage_noise_row("https://github.com/acme/repo", "PR review"))

    def test_filter_triage_noise_rows_drops_noise_rows(self):
        rows = [
            (1, "https://cursor.sh/docs", "Cursor Docs"),
            (2, "https://example.com", "Canvas SDK mirror failed"),
            (3, "https://github.com/acme/repo", "Implement feature"),
        ]
        filtered, dropped = _filter_triage_noise_rows(rows)
        self.assertEqual(dropped, 2)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0][1], "https://github.com/acme/repo")

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

    def test_load_triage_profiles_preserves_explicit_empty_config(self):
        raw = '{"version": 1, "projects": []}'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        try:
            self.assertEqual(load_triage_profiles(path), [])
        finally:
            Path(path).unlink(missing_ok=True)

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
        self.assertEqual(plan["days"][0]["noise_rows_filtered"], 0)

    @patch("core.report_service.run_timelog_report")
    def test_build_triage_plan_filters_noise_rows_before_scoring(self, mock_run):
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
            (132_537_602_000_000, "https://cursor.sh/docs", "Cursor Docs"),
            (132_537_603_000_000, "https://example.com", "Canvas SDK mirror failed"),
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
        self.assertEqual(len(top_sites), 1)
        self.assertEqual(top_sites[0]["domain"], "github.com")
        self.assertEqual(
            plan["days"][0]["code_repos"],
            [{"provider": "github", "value": "github.com/mbjorke/timelog-extract", "visits": 1}],
        )
        self.assertEqual(plan["days"][0]["noise_rows_filtered"], 2)

    @patch("core.report_service.run_timelog_report")
    def test_build_triage_plan_includes_guided_config_dry_run(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            dt_from=None,
            dt_to=None,
            args=SimpleNamespace(min_session=15, min_session_passive=5),
            overall_days={},
            project_reports={},
            screen_time_days={},
        )
        raw = (
            '{"version": 1, "projects": ['
            '{"name": "Acme", "canonical_project": "Acme", '
            '"tracked_urls": [], "match_terms": ["shared"]},'
            '{"name": "Other", "canonical_project": "Other", '
            '"tracked_urls": [], "match_terms": ["shared"]}'
            "]}"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        gap_payload = {
            "days": [
                {
                    "day": "2026-04-21",
                    "estimated_hours": 1.0,
                    "screen_time_hours": 2.0,
                    "unexplained_screen_time_hours": 1.0,
                }
            ]
        }
        chrome_rows = [
            (132_537_602_000_000, "https://acme.example.com/dashboard", "Acme dashboard"),
            (132_537_605_000_000, "https://docs.acme.example.com/api", "Acme API"),
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
        guided = plan["guided_config"]
        self.assertEqual(guided["mode"], "evidence-review")
        self.assertIn("candidates", guided)
        self.assertIn("config_warnings", guided)
        self.assertNotIn("update", guided)
        self.assertTrue(any(item["candidate_type"] == "domain" for item in guided["candidates"]))
        self.assertTrue(any(item["code"] == "overlap-term" for item in guided["config_warnings"]))
        self.assertIn("explicit decisions", " ".join(guided["next_steps"]))

    @patch("core.report_service.run_timelog_report")
    def test_build_triage_plan_yes_automation_blocks_weak_project_domains(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            dt_from=None,
            dt_to=None,
            args=SimpleNamespace(min_session=15, min_session_passive=5),
            overall_days={},
            project_reports={},
            screen_time_days={},
        )
        raw = (
            '{"version": 1, "projects": ['
            '{"name": "Acme API", "canonical_project": "Acme API", '
            '"tracked_urls": [], "match_terms": ["dashboard"]},'
            '{"name": "Client Docs", "canonical_project": "Client Docs", '
            '"tracked_urls": [], "match_terms": ["docs"]}'
            "]}"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        gap_payload = {
            "days": [
                {
                    "day": "2026-04-08",
                    "estimated_hours": 3.0,
                    "screen_time_hours": 10.0,
                    "unexplained_screen_time_hours": 7.0,
                }
            ]
        }
        chrome_rows = [
            (132_537_602_000_000, "https://dashboard.example.com/app", "dashboard"),
            (132_537_605_000_000, "https://docs.vendor.test/guides", "docs"),
            (132_537_606_000_000, "https://search.example.net/work", "search"),
        ]
        try:
            with patch("core.cli_triage.analyze_screen_time_gaps", return_value=gap_payload), patch(
                "core.cli_triage.fetch_chrome_rows_for_day", return_value=chrome_rows
            ):
                plan = build_triage_plan_dict(
                    date_from=None,
                    date_to=None,
                    projects_config=path,
                    max_days=1,
                    max_sites=3,
                    scoring_mode="site-first",
                )
        finally:
            Path(path).unlink(missing_ok=True)
        automation = plan["days"][0]["yes_automation"]
        self.assertFalse(automation["would_apply"])
        self.assertEqual(automation["reason"], "explicit_decision_required")
        self.assertEqual(automation["target_project"], "Acme API")

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

    def test_triage_yes_is_disabled(self):
        repo = Path(__file__).resolve().parent.parent
        r = subprocess.run(
            [sys.executable, str(repo / "timelog_extract.py"), "triage", "--yes"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no longer applies heuristic mappings", r.stdout + r.stderr)


def _make_suggestion(canonical: str, score: int = 10) -> ProjectSuggestion:
    return ProjectSuggestion(
        canonical=canonical,
        score=score,
        aliases=[canonical],
        explicit_domain_hits=1,
        term_hits=0,
        alias_or_name_hits=0,
        ticket_mode="optional",
        default_client=canonical,
    )


class TriageJsonExtensionTests(unittest.TestCase):
    def test_tags_field_in_suggestion_dict(self):
        s = _make_suggestion("Briox Dev")
        d = _suggestion_to_plan_dict(s, ["tech"])
        self.assertEqual(d["tags"], ["tech"])
        self.assertEqual(d["canonical"], "Briox Dev")

    def test_question_and_choices_present(self):
        suggestions = [_make_suggestion("Briox Dev"), _make_suggestion("Maintenance")]
        gap = {"day": "2026-04-15", "unexplained_screen_time_hours": 2.5}
        q = _build_question(gap, suggestions)
        self.assertIsNotNone(q)
        self.assertIn("Briox Dev", q)
        self.assertIn("Maintenance", q)

        choices = _build_choices(suggestions, {"Briox Dev": ["tech"], "Maintenance": ["ops"]})
        self.assertEqual(len(choices), 3)
        self.assertIsNone(choices[-1]["canonical"])
        self.assertEqual(choices[0]["canonical"], "Briox Dev")
        self.assertEqual(choices[0]["tags"], ["tech"])
        self.assertIn("TECH", choices[0]["label"])

    def test_question_is_none_when_no_suggestions(self):
        gap = {"day": "2026-04-15", "unexplained_screen_time_hours": 1.0}
        self.assertIsNone(_build_question(gap, []))
        choices = _build_choices([], {})
        self.assertEqual(len(choices), 1)
        self.assertIsNone(choices[0]["canonical"])

    def test_question_single_suggestion(self):
        """Single suggestion yields a question mentioning only that project."""
        suggestions = [_make_suggestion("MyProject")]
        gap = {"day": "2026-04-10", "unexplained_screen_time_hours": 1.5}
        q = _build_question(gap, suggestions)
        self.assertIsNotNone(q)
        self.assertIn("MyProject", q)
        self.assertIn("1.5h", q)
        self.assertIn("2026-04-10", q)
        # Single-suggestion question should not reference a second project
        self.assertNotIn(" or ", q)

    def test_suggestion_to_plan_dict_with_empty_tags(self):
        """_suggestion_to_plan_dict with an empty tags list emits an empty list."""
        s = _make_suggestion("NoTagProject")
        d = _suggestion_to_plan_dict(s, [])
        self.assertEqual(d["tags"], [])
        self.assertEqual(d["canonical"], "NoTagProject")

    def test_build_choices_label_uses_proj_prefix_when_no_tags(self):
        """When a suggestion has no tags, label uses generic #PROJ prefix (no tag dash suffix)."""
        suggestions = [_make_suggestion("Orphan")]
        choices = _build_choices(suggestions, {})
        # First entry should be the suggestion, last is skip
        self.assertEqual(choices[0]["canonical"], "Orphan")
        self.assertIn("#PROJ ·", choices[0]["label"])
        # No tag-specific prefix like #PROJ-TECH when there are no tags
        self.assertNotIn("#PROJ-", choices[0]["label"])

    def test_build_choices_max_choices_limits_suggestions(self):
        """max_choices=2 means only 1 suggestion + the skip sentinel."""
        suggestions = [_make_suggestion(f"P{i}") for i in range(5)]
        choices = _build_choices(suggestions, {}, max_choices=2)
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0]["canonical"], "P0")
        self.assertIsNone(choices[-1]["canonical"])

    def test_build_choices_always_ends_with_skip_sentinel(self):
        """The last choice is always the 'None of these / skip' sentinel."""
        suggestions = [_make_suggestion("A"), _make_suggestion("B"), _make_suggestion("C")]
        choices = _build_choices(suggestions, {})
        self.assertIsNone(choices[-1]["canonical"])
        self.assertIn("skip", choices[-1]["label"].lower())

    def test_build_question_hours_formatted_correctly(self):
        """Hours in the question are formatted to one decimal place."""
        suggestions = [_make_suggestion("Alpha")]
        gap = {"day": "2026-04-20", "unexplained_screen_time_hours": 3.0}
        q = _build_question(gap, suggestions)
        self.assertIn("3.0h", q)

    def test_build_choices_tag_prefix_uppercased(self):
        """Tag in the label prefix is uppercased."""
        suggestions = [_make_suggestion("Dev")]
        choices = _build_choices(suggestions, {"Dev": ["backend"]})
        self.assertIn("BACKEND", choices[0]["label"])


if __name__ == "__main__":
    unittest.main()