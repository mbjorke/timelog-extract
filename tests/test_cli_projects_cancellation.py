"""Integration and UX regression tests for `gittan` interactive cancellations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from core.cli_triage_map_candidates import UrlCandidate


def _fake_row():
    return UrlCandidate(
        title="Example",
        url_key="customer-a.test",
        suggested_project="Uncategorized",
        confidence_label="low",
        confidence_score=0.0,
        impact_hours=0.0,
        events=3,
        days=1,
        last_seen="2026-07-21",
        sample_urls=["https://customer-a.test/"],
    )


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

    def test_review_command_cancellation_exits_130(self):
        runner = CliRunner()
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            config_path.write_text(json.dumps({"projects": [{"name": "project-alpha", "match_terms": ["alpha"]}]}), encoding="utf-8")

            report = mock.Mock(profiles=[{"name": "project-alpha", "match_terms": ["alpha"]}], all_events=[], included_events=[], dt_from=None, dt_to=None)
            with patch("core.cli_url_mapping.should_prompt", return_value=True), \
                 patch("core.cli_url_mapping.load_triage_map_session", return_value=([_fake_row()], report)), \
                 patch("core.cli_url_mapping.run_review_new_remotes_step", return_value=False), \
                 patch("core.cli_url_mapping.questionary.confirm") as confirm_mock, \
                 patch("core.cli_url_mapping.questionary.select") as select_mock, \
                 patch("core.cli_url_mapping._prompt_project_for_row") as prompt_row_mock, \
                 patch("core.cli_url_mapping.apply_triage_decisions_payload") as apply_mock:

                # select_mock.side_effect returns ask results:
                # 1. Bulk apply suggestion -> "none"
                # 2. Edit mappings row-by-row (1st iteration) -> "customer-a.test"
                # 3. Edit mappings row-by-row (2nd iteration) -> "__done__"
                select_mock.return_value.ask.side_effect = ["none", "customer-a.test", "__done__"]

                # confirm_mock.side_effect returns ask results:
                # 1. "Review/edit remaining rows manually before apply?" -> True
                # 2. "Apply these URL mappings now?" -> None (Cancel/Abort)
                confirm_mock.return_value.ask.side_effect = [True, None]

                prompt_row_mock.return_value = ("project-alpha", ["project-alpha"], {"project-alpha"})
                apply_mock.return_value = {"preview": "Preview text"}

                result = runner.invoke(app, ["review", "--projects-config", str(config_path), "--last-week"])

            self.assertEqual(result.exit_code, 130)

    def test_review_command_decline_exits_0(self):
        runner = CliRunner()
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            config_path.write_text(json.dumps({"projects": [{"name": "project-alpha", "match_terms": ["alpha"]}]}), encoding="utf-8")

            report = mock.Mock(profiles=[{"name": "project-alpha", "match_terms": ["alpha"]}], all_events=[], included_events=[], dt_from=None, dt_to=None)
            with patch("core.cli_url_mapping.should_prompt", return_value=True), \
                 patch("core.cli_url_mapping.load_triage_map_session", return_value=([_fake_row()], report)), \
                 patch("core.cli_url_mapping.run_review_new_remotes_step", return_value=False), \
                 patch("core.cli_url_mapping.questionary.confirm") as confirm_mock, \
                 patch("core.cli_url_mapping.questionary.select") as select_mock, \
                 patch("core.cli_url_mapping._prompt_project_for_row") as prompt_row_mock, \
                 patch("core.cli_url_mapping.apply_triage_decisions_payload") as apply_mock, \
                 patch("core.cli_url_mapping.finish_review_guidance") as finish_mock:

                # select_mock.side_effect returns ask results:
                # 1. Bulk apply suggestion -> "none"
                # 2. Edit mappings row-by-row (1st iteration) -> "customer-a.test"
                # 3. Edit mappings row-by-row (2nd iteration) -> "__done__"
                select_mock.return_value.ask.side_effect = ["none", "customer-a.test", "__done__"]

                # confirm_mock.side_effect returns ask results:
                # 1. "Review/edit remaining rows manually before apply?" -> True
                # 2. "Apply these URL mappings now?" -> False (Decline/No)
                confirm_mock.return_value.ask.side_effect = [True, False]

                prompt_row_mock.return_value = ("project-alpha", ["project-alpha"], {"project-alpha"})
                apply_mock.return_value = {"preview": "Preview text"}

                result = runner.invoke(app, ["review", "--projects-config", str(config_path), "--last-week"])

            self.assertEqual(result.exit_code, 0)
            finish_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
