from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class TriageGuidedTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _config_path(self) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(json.dumps({"projects": [{"name": "Demo", "match_terms": [], "tracked_urls": []}]}))
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_guided_happy_path_applies_after_confirm(self):
        plan = {
            "days": [
                {
                    "day": "2026-04-30",
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                }
            ],
            "project_names": ["Demo"],
        }
        cfg = self._config_path()
        with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
            "core.cli_triage_guided.questionary.confirm"
        ) as confirm_mock, patch("core.cli_triage_guided.questionary.checkbox") as checkbox_mock, patch(
            "core.cli_triage_guided.apply_triage_decisions_payload"
        ) as apply_mock:
            confirm_mock.return_value.ask.side_effect = [True, True]
            checkbox_mock.return_value.ask.return_value = ["demo.test"]
            apply_mock.side_effect = [
                {"dry_run": True, "preview": "Planned config updates:", "would_apply": [], "skipped": 0, "errors": []},
                {"applied": 1, "skipped": 0, "preview": "Planned config updates:", "errors": []},
            ]
            result = self.runner.invoke(app, ["triage-guided", "--projects-config", cfg])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Guided triage apply complete", result.output)
        self.assertEqual(apply_mock.call_count, 2)

    def test_guided_cancel_path_skips_write(self):
        plan = {
            "days": [
                {
                    "day": "2026-04-30",
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                }
            ],
            "project_names": ["Demo"],
        }
        cfg = self._config_path()
        with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
            "core.cli_triage_guided.questionary.confirm"
        ) as confirm_mock, patch("core.cli_triage_guided.questionary.checkbox") as checkbox_mock, patch(
            "core.cli_triage_guided.apply_triage_decisions_payload"
        ) as apply_mock:
            confirm_mock.return_value.ask.side_effect = [True, False]
            checkbox_mock.return_value.ask.return_value = ["demo.test"]
            apply_mock.return_value = {
                "dry_run": True,
                "preview": "Planned config updates:",
                "would_apply": [],
                "skipped": 0,
                "errors": [],
            }
            result = self.runner.invoke(app, ["triage-guided", "--projects-config", cfg])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Cancelled before writing config", result.output)
        self.assertEqual(apply_mock.call_count, 1)

    def test_guided_write_decisions_file_uses_apply_schema(self):
        plan = {
            "days": [
                {
                    "day": "2026-04-30",
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}, {"domain": "docs.demo.test"}],
                }
            ],
            "project_names": ["Demo"],
        }
        cfg = self._config_path()
        with tempfile.TemporaryDirectory() as tmp_dir:
            decisions_path = Path(tmp_dir) / "nested" / "decisions.json"
            with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
                "core.cli_triage_guided.questionary.confirm"
            ) as confirm_mock, patch("core.cli_triage_guided.questionary.checkbox") as checkbox_mock, patch(
                "core.cli_triage_guided.apply_triage_decisions_payload"
            ) as apply_mock:
                confirm_mock.return_value.ask.side_effect = [True, False]
                checkbox_mock.return_value.ask.return_value = ["demo.test", "docs.demo.test"]
                apply_mock.return_value = {
                    "dry_run": True,
                    "preview": "Planned config updates:",
                    "would_apply": [],
                    "skipped": 0,
                    "errors": [],
                }
                result = self.runner.invoke(
                    app,
                    [
                        "triage-guided",
                        "--projects-config",
                        cfg,
                        "--write-decisions",
                        str(decisions_path),
                    ],
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Decisions file written:", result.output)
            payload = json.loads(decisions_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["decisions"],
                [
                    {"project_name": "Demo", "rule_type": "tracked_urls", "rule_value": "demo.test"},
                    {"project_name": "Demo", "rule_type": "tracked_urls", "rule_value": "docs.demo.test"},
                ],
            )
            self.assertEqual(apply_mock.call_count, 1)

    def test_guided_no_decisions_does_not_write_file(self):
        plan = {
            "days": [
                {
                    "day": "2026-04-30",
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                }
            ],
            "project_names": ["Demo"],
        }
        cfg = self._config_path()
        with tempfile.TemporaryDirectory() as tmp_dir:
            decisions_path = Path(tmp_dir) / "decisions.json"
            with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
                "core.cli_triage_guided.questionary.confirm"
            ) as confirm_mock, patch("core.cli_triage_guided.questionary.checkbox") as checkbox_mock, patch(
                "core.cli_triage_guided.apply_triage_decisions_payload"
            ) as apply_mock:
                confirm_mock.return_value.ask.return_value = True
                checkbox_mock.return_value.ask.return_value = []
                result = self.runner.invoke(
                    app,
                    [
                        "triage-guided",
                        "--projects-config",
                        cfg,
                        "--write-decisions",
                        str(decisions_path),
                    ],
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Decisions file not written", result.output)
            self.assertFalse(decisions_path.exists())
            self.assertEqual(apply_mock.call_count, 0)

    def test_guided_no_gap_but_uncategorized_shows_actionable_fallback(self):
        plan = {"days": [], "project_names": ["Demo"]}
        cfg = self._config_path()
        fallback_report = SimpleNamespace(
            overall_days={"2026-04-30": {"hours": 4.0}},
            project_reports={"Uncategorized": {"2026-04-30": {"hours": 3.9}}},
            screen_time_days={"2026-04-30": 4.0 * 3600.0},
        )
        with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
            "core.report_service.run_timelog_report",
            return_value=fallback_report,
        ):
            result = self.runner.invoke(
                app,
                ["triage-guided", "--projects-config", cfg, "--from", "2026-04-30", "--to", "2026-04-30"],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Uncategorized time is significant", result.output)
        self.assertIn("gittan triage --json", result.output)
        self.assertIn("triage-apply", result.output)

    def test_guided_fallback_write_decisions_writes_scaffold_file(self):
        plan = {"days": [], "project_names": ["Demo"]}
        cfg = self._config_path()
        fallback_report = SimpleNamespace(
            overall_days={"2026-04-30": {"hours": 4.0}},
            project_reports={"Uncategorized": {"2026-04-30": {"hours": 3.9}}},
            screen_time_days={"2026-04-30": 4.0 * 3600.0},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            decisions_path = Path(tmp_dir) / "fallback-decisions.json"
            with patch("core.cli_triage_guided.build_triage_plan_dict", return_value=plan), patch(
                "core.report_service.run_timelog_report",
                return_value=fallback_report,
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "triage-guided",
                        "--projects-config",
                        cfg,
                        "--from",
                        "2026-04-30",
                        "--to",
                        "2026-04-30",
                        "--write-decisions",
                        str(decisions_path),
                    ],
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Scaffold decisions file written:", result.output)
            payload = json.loads(decisions_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["decisions"], [])


if __name__ == "__main__":
    unittest.main()
