"""Integration and UX regression tests for `gittan projects` interactive cancellations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliProjectsCancellationTests(unittest.TestCase):
    def test_projects_command_cancellation_exits_130(self):
        runner = CliRunner()
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            # Write a valid starting config
            config_path.write_text(json.dumps({"projects": []}), encoding="utf-8")

            # Patch questionary.select to return None (representing Cancel/Ctrl+C)
            with patch("core.cli_projects.questionary.select") as select_mock:
                select_mock.return_value.ask.return_value = None
                result = runner.invoke(app, ["projects", "--config", str(config_path)])

            self.assertEqual(result.exit_code, 130)
            # Ensure config is unmodified
            data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"projects": []})


class UrlMappingConfirmTests(unittest.TestCase):
    """The final apply prompt must tell Ctrl+C apart from a deliberate "no".

    questionary returns None for the former and False for the latter. Routing
    both to exit 130 reports a considered "don't apply" as an interrupted
    command to shells, wrappers and CI.
    """

    def _run(self, confirm_value):
        import typer

        from core.cli_triage_map_candidates import UrlCandidate
        from core.cli_url_mapping import run_url_mapping_review

        row = UrlCandidate(
            title="project-alpha board",
            url_key="example.test/alpha",
            suggested_project="project-alpha",
            confidence_label="high",
            confidence_score=0.9,
            impact_hours=1.5,
            events=4,
            days=2,
            last_seen="2026-08-04",
            sample_urls=["https://example.test/alpha"],
        )
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            original = {"projects": [{"name": "project-alpha", "match_terms": ["alpha"]}]}
            config_path.write_text(json.dumps(original), encoding="utf-8")

            mod = "core.cli_url_mapping"
            with patch(f"{mod}.should_prompt", return_value=True), \
                 patch(f"{mod}.load_triage_map_session", return_value=([row], {})), \
                 patch(f"{mod}.load_triage_profiles", return_value=original["projects"]), \
                 patch(f"{mod}.run_review_new_remotes_step", return_value=False), \
                 patch(f"{mod}.partition_candidates", return_value=([row], [])), \
                 patch(f"{mod}._render_candidates_table"), \
                 patch(f"{mod}.apply_triage_decisions_payload", return_value={"preview": "ok"}) as apply_mock, \
                 patch(f"{mod}.questionary") as q:
                # Bulk-apply everything, so a decision exists to confirm.
                q.select.return_value.ask.return_value = "all"
                q.confirm.return_value.ask.return_value = confirm_value

                code = 0
                try:
                    run_url_mapping_review(today=True, projects_config=str(config_path))
                except typer.Exit as exc:
                    code = exc.exit_code

            unchanged = json.loads(config_path.read_text(encoding="utf-8")) == original
            # dry_run=False means a real write was attempted.
            wrote = any(
                call.kwargs.get("dry_run") is False for call in apply_mock.call_args_list
            )
            return code, unchanged, wrote

    def test_ctrl_c_at_apply_prompt_exits_130(self):
        code, unchanged, wrote = self._run(None)
        self.assertEqual(code, 130)
        self.assertTrue(unchanged)
        self.assertFalse(wrote)

    def test_declining_at_apply_prompt_exits_0_without_writing(self):
        code, unchanged, wrote = self._run(False)
        self.assertEqual(code, 0, "answering no is a completed review, not an interrupt")
        self.assertTrue(unchanged)
        self.assertFalse(wrote)


if __name__ == "__main__":
    unittest.main()
