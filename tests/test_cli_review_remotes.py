"""New remotes step inside `gittan review` (#419)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.cli_review_remotes import (
    build_review_remote_mapping,
    new_remote_candidates_payload,
    run_review_new_remotes_step,
)
from core.mapping_review import MappingReview, NewProjectProposal


class ReviewRemotesStepTests(unittest.TestCase):
    def test_payload_serializes_new_remotes_only(self):
        review = MappingReview(
            new_projects=[
                NewProjectProposal(
                    slug="acme/project-alpha",
                    url="https://github.com/acme/project-alpha.git",
                    created_at="2026-07-01",
                    suggested_name="project-alpha",
                    local_path="/tmp/project-alpha",
                )
            ]
        )
        rows = new_remote_candidates_payload(review)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "acme/project-alpha")
        self.assertEqual(rows[0]["suggested_name"], "project-alpha")
        self.assertEqual(rows[0]["url"], "https://github.com/acme/project-alpha.git")

    @patch("core.cli_review_remotes.build_mapping_review")
    def test_build_uses_report_events_and_profiles(self, build_mock):
        build_mock.return_value = MappingReview()
        report = SimpleNamespace(
            profiles=[{"name": "project-beta", "match_terms": ["project-beta"]}],
            all_events=[{"source": "GitHub", "detail": "acme/project-alpha"}],
            included_events=[],
            dt_from=None,
            dt_to=None,
        )
        build_review_remote_mapping(report)
        build_mock.assert_called_once()
        args, kwargs = build_mock.call_args
        self.assertEqual(args[0], report.all_events)
        self.assertEqual(args[1], report.profiles)
        self.assertIsNone(kwargs.get("extra_signals"))

    @patch("core.cli_review_remotes.run_interactive_mapping_flow", return_value=2)
    @patch("core.cli_review_remotes.build_review_remote_mapping")
    def test_interactive_step_runs_batch_flow_when_remotes_exist(self, review_mock, flow_mock):
        review_mock.return_value = MappingReview(
            new_projects=[
                NewProjectProposal(
                    slug="acme/project-alpha",
                    url="https://github.com/acme/project-alpha.git",
                    created_at=None,
                    suggested_name="project-alpha",
                )
            ]
        )
        console = MagicMock()
        report = SimpleNamespace(profiles=[{"name": "project-beta"}], all_events=[], included_events=[])
        applied = run_review_new_remotes_step(
            console,
            report,
            projects_config="/tmp/timelog_projects.json",
            profiles=[{"name": "project-beta"}],
        )
        self.assertEqual(applied, 2)
        flow_mock.assert_called_once()
        printed = " ".join(str(c.args[0]) for c in console.print.call_args_list if c.args)
        self.assertIn("New remote repositories", printed)
        self.assertIn("timestamped backup", printed)

    @patch("core.cli_review_remotes.run_interactive_mapping_flow")
    @patch("core.cli_review_remotes.build_review_remote_mapping")
    def test_interactive_step_skips_when_no_remotes(self, review_mock, flow_mock):
        review_mock.return_value = MappingReview()
        applied = run_review_new_remotes_step(
            MagicMock(),
            SimpleNamespace(profiles=[], all_events=[], included_events=[]),
            projects_config="/tmp/timelog_projects.json",
        )
        self.assertEqual(applied, 0)
        flow_mock.assert_not_called()

    @patch("core.cli_url_mapping.run_review_new_remotes_step", return_value=1)
    @patch("core.cli_url_mapping.load_triage_profiles")
    @patch("core.cli_url_mapping.load_triage_map_session")
    @patch("core.cli_url_mapping.should_prompt", return_value=True)
    def test_review_runs_remotes_before_empty_url_exit(
        self,
        _tty,
        session_mock,
        profiles_mock,
        remotes_mock,
    ):
        import typer

        from core import cli_url_mapping

        report = SimpleNamespace(profiles=[], all_events=[], included_events=[], dt_from=None, dt_to=None)
        session_mock.return_value = ([], report)
        profiles_mock.side_effect = [
            [],
            [{"name": "project-alpha", "match_terms": ["acme/project-alpha", "project-alpha"]}],
        ]
        console = MagicMock()
        with patch.object(cli_url_mapping, "Console", return_value=console):
            with self.assertRaises(typer.Exit) as ctx:
                cli_url_mapping.run_url_mapping_review(today=True, json_out=False)
        self.assertEqual(ctx.exception.exit_code, 0)
        remotes_mock.assert_called_once()
        self.assertEqual(profiles_mock.call_count, 2)
        printed = " ".join(str(c.args[0]) for c in console.print.call_args_list if c.args)
        self.assertIn("Remote mapping saved", printed)


if __name__ == "__main__":
    unittest.main()
