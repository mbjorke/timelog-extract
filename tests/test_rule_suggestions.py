"""Tests for A/B uncategorized rule suggestions, preview impact, and apply flow."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core.config import apply_rule_to_project, load_projects_config_payload, save_projects_config_payload
from core.config import backup_projects_config_if_exists
from core.rule_suggestions import (
    ab_suggestions_state_path,
    preview_suggestion_impact,
    split_ab_suggestions,
    write_suggestions_state,
)
from core.uncategorized_review import UncategorizedCluster, build_uncategorized_clusters


def _prof(name: str, terms: list[str], urls: list[str] | None = None):
    return {
        "name": name,
        "match_terms": sorted({t.lower() for t in terms + [name] if t}),
        "tracked_urls": list(urls or []),
        "enabled": True,
        "email": "",
        "customer": name,
        "invoice_title": "",
        "invoice_description": "",
    }


class RuleSuggestionsABSplitTests(unittest.TestCase):
    def test_b_is_superset_and_b_has_extra_medium_terms(self):
        clusters = [
            UncategorizedCluster(
                key="u:acme-app.example:Chrome",
                rule_type="tracked_urls",
                rule_value="acme-app.example",
                source="Chrome",
                count=2,
                samples=["https://acme-app.example/a", "https://acme-app.example/b"],
            ),
            UncategorizedCluster(
                key="m:zeta:Cursor",
                rule_type="match_terms",
                rule_value="zeta",
                source="Cursor",
                count=2,
                samples=["zeta one", "zeta two"],
            ),
        ]
        profiles = [_prof("Target", ["target"])]
        opt_a, opt_b = split_ab_suggestions(clusters, profiles, "Target")

        keys_a = {(r.rule_type, r.rule_value) for r in opt_a}
        keys_b = {(r.rule_type, r.rule_value) for r in opt_b}
        self.assertTrue(keys_a.issubset(keys_b))
        self.assertGreater(len(opt_b), len(opt_a))
        self.assertIn(("tracked_urls", "acme-app.example"), keys_a)
        # Repeated 4-letter term: medium bucket → B only, not A (safe needs len≥8 or strong shape)
        self.assertIn(("match_terms", "zeta"), keys_b)
        self.assertNotIn(("match_terms", "zeta"), keys_a)

    def test_filters_meta_noise_match_terms_from_broad_suggestions(self):
        clusters = [
            UncategorizedCluster(
                key="m:commit:TIMELOG.md",
                rule_type="match_terms",
                rule_value="commit",
                source="TIMELOG.md",
                count=9,
                samples=["- Commit: docs cleanup", "- Commit: release prep"],
            ),
            UncategorizedCluster(
                key="m:checkoutsuccess:Chrome",
                rule_type="match_terms",
                rule_value="checkoutsuccess",
                source="Chrome",
                count=2,
                samples=["https://example.com/CheckoutSuccess", "CheckoutSuccess page"],
            ),
        ]
        profiles = [_prof("Target", ["target"])]
        opt_a, opt_b = split_ab_suggestions(clusters, profiles, "Target")
        keys_a = {(r.rule_type, r.rule_value) for r in opt_a}
        keys_b = {(r.rule_type, r.rule_value) for r in opt_b}
        self.assertNotIn(("match_terms", "commit"), keys_a)
        self.assertNotIn(("match_terms", "commit"), keys_b)
        self.assertIn(("match_terms", "checkoutsuccess"), keys_b)

    def test_sanitizes_tracked_url_with_control_char_noise(self):
        clusters = [
            UncategorizedCluster(
                key="u:lovable-dev-noise:Lovable (desktop)",
                rule_type="tracked_urls",
                rule_value="lovable.dev\x014:e",
                source="Lovable (desktop)",
                count=1,
                samples=["storage signal — https://lovable.dev\x014:e"],
            )
        ]
        profiles = [_prof("Target", ["target"])]
        opt_a, opt_b = split_ab_suggestions(clusters, profiles, "Target")
        keys_a = {(r.rule_type, r.rule_value) for r in opt_a}
        keys_b = {(r.rule_type, r.rule_value) for r in opt_b}
        self.assertIn(("tracked_urls", "lovable.dev"), keys_a)
        self.assertIn(("tracked_urls", "lovable.dev"), keys_b)

    def test_ignores_match_term_clusters_from_timelog_source(self):
        clusters = [
            UncategorizedCluster(
                key="m:changelog:TIMELOG.md",
                rule_type="match_terms",
                rule_value="changelog",
                source="TIMELOG.md",
                count=3,
                samples=["- Commit: update changelog"],
            )
        ]
        profiles = [_prof("Target", ["target"])]
        opt_a, opt_b = split_ab_suggestions(clusters, profiles, "Target")
        self.assertEqual(opt_a, [])
        self.assertEqual(opt_b, [])


class RuleSuggestionsPreviewTests(unittest.TestCase):
    def test_preview_counts_events_and_hours(self):
        tz = timezone.utc
        ts1 = datetime(2026, 4, 10, 9, 0, tzinfo=tz)
        ts2 = datetime(2026, 4, 10, 9, 30, tzinfo=tz)
        uncategorized_events = [
            {
                "source": "Chrome",
                "detail": "https://client-only.example/tasks",
                "project": "Uncategorized",
                "timestamp": ts1,
            },
            {
                "source": "Chrome",
                "detail": "https://client-only.example/tasks more",
                "project": "Uncategorized",
                "timestamp": ts2,
            },
        ]
        profiles = [_prof("Client", ["client"])]
        clusters = build_uncategorized_clusters(uncategorized_events, max_clusters=10, samples_per_cluster=2)
        opt_a, _opt_b = split_ab_suggestions(clusters, profiles, "Client")
        self.assertTrue(any(r.rule_type == "tracked_urls" for r in opt_a))

        me, hours, delta = preview_suggestion_impact(
            uncategorized_events,
            profiles,
            "Client",
            opt_a,
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            exclude_keywords=[],
        )
        self.assertEqual(me, 2)
        self.assertGreater(hours, 0.0)
        self.assertEqual(delta, -2)


class ApplySuggestionsBackupTests(unittest.TestCase):
    def test_backup_and_apply_from_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            payload = {"projects": [_prof("Acme", ["acme"])]}
            save_projects_config_payload(cfg, payload)

            opt_preview = {
                "A": {
                    "rules": [
                        {
                            "rule_type": "match_terms",
                            "rule_value": "special-token",
                            "cluster_count": 2,
                            "source": "Cursor",
                            "samples": ["a", "b"],
                            "note": "test",
                        }
                    ],
                    "preview": {"matched_events": 1, "matched_hours": 0.5, "uncategorized_delta": -1},
                },
                "B": {
                    "rules": [],
                    "preview": {"matched_events": 0, "matched_hours": 0.0, "uncategorized_delta": 0},
                },
            }
            state_path = ab_suggestions_state_path(cfg)
            write_suggestions_state(
                state_path,
                projects_config=str(cfg),
                target_project="Acme",
                uncategorized_total=3,
                option_previews=opt_preview,
            )

            from core.rule_suggestions import rules_from_state_option

            state = json.loads(state_path.read_text(encoding="utf-8"))
            rules = rules_from_state_option(state, "A")
            self.assertEqual(len(rules), 1)

            backup = backup_projects_config_if_exists(cfg)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.is_file())

            loaded = load_projects_config_payload(cfg)
            for suggestion in rules:
                apply_rule_to_project(
                    loaded,
                    project_name=state["target_project"],
                    rule_type=suggestion.rule_type,
                    rule_value=suggestion.rule_value,
                )
            save_projects_config_payload(cfg, loaded)

            final = load_projects_config_payload(cfg)
            acme = final["projects"][0]
            self.assertIn("special-token", acme["match_terms"])


class ApplySuggestionsCliTests(unittest.TestCase):
    def test_apply_invokes_save_when_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": [_prof("Acme", ["acme"])]})
            write_suggestions_state(
                ab_suggestions_state_path(cfg),
                projects_config=str(cfg),
                target_project="Acme",
                uncategorized_total=1,
                option_previews={
                    "A": {
                        "rules": [
                            {
                                "rule_type": "match_terms",
                                "rule_value": "cli-token",
                                "cluster_count": 1,
                                "source": "X",
                                "samples": [],
                                "note": "",
                            }
                        ],
                        "preview": {},
                    },
                    "B": {"rules": [], "preview": {}},
                },
            )

            from typer.testing import CliRunner

            from core.cli import app

            runner = CliRunner()
            with mock.patch("core.cli_ab_rule_suggestions.save_projects_config_payload") as save_mock:
                result = runner.invoke(
                    app,
                    ["apply-suggestions", "--projects-config", str(cfg), "--option", "A", "--confirm"],
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            save_mock.assert_called_once()


class SuggestRulesCliUxTests(unittest.TestCase):
    def test_prompts_for_project_when_option_missing(self):
        from typer.testing import CliRunner

        from core.cli import app

        runner = CliRunner()
        fake_report = mock.Mock(
            included_events=[{"project": "Uncategorized", "source": "Cursor", "detail": "x", "timestamp": datetime.now(timezone.utc)}]
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": [_prof("Acme", ["acme"])]})
            with mock.patch("core.cli_ab_rule_suggestions.questionary.text") as prompt_mock, mock.patch(
                "core.report_service.run_timelog_report", return_value=fake_report
            ), mock.patch("core.cli_ab_rule_suggestions.gather_ab_suggestions", return_value=([], [], (0, 0.0, 0), (0, 0.0, 0))), mock.patch(
                "core.cli_ab_rule_suggestions.persist_suggestion_state", return_value=Path(tmp) / ".state.json"
            ):
                prompt_mock.return_value.ask.return_value = "Acme"
                result = runner.invoke(app, ["suggest-rules", "--today", "--projects-config", str(cfg)])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("A/B rule suggestions", result.output)

    def test_missing_project_after_prompt_shows_helpful_error(self):
        from typer.testing import CliRunner

        from core.cli import app

        runner = CliRunner()
        fake_report = mock.Mock(
            included_events=[{"project": "Uncategorized", "source": "Cursor", "detail": "x", "timestamp": datetime.now(timezone.utc)}]
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": [_prof("Acme", ["acme"])]})
            with mock.patch("core.cli_ab_rule_suggestions.questionary.text") as prompt_mock, mock.patch(
                "core.report_service.run_timelog_report", return_value=fake_report
            ):
                prompt_mock.return_value.ask.return_value = ""
                result = runner.invoke(app, ["suggest-rules", "--today", "--projects-config", str(cfg)])
        self.assertEqual(result.exit_code, 1, msg=result.output)
        self.assertIn("Project name is required.", result.output)
        self.assertIn("--project <name>", result.output)


if __name__ == "__main__":
    unittest.main()
