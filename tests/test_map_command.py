"""Tests for simplified `gittan map` flow."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.map_command import map_exit_message, run_map_command
from core.map_repo_hints import unconfigured_repo_slugs_in_events
from core.mapping_review import MappingReview


class UnconfiguredRepoSlugsTests(unittest.TestCase):
    def test_ignores_mapped_slugs_and_dot_repos(self) -> None:
        profiles = [
            {
                "name": "project-alpha",
                "match_terms": ["mbjorke/project-alpha"],
            }
        ]
        events = [
            {
                "source": "GitHub",
                "detail": "created mbjorke/new-repo",
                "anchors": {"repo": "mbjorke/new-repo"},
            },
            {
                "source": "Cursor",
                "detail": "config edit",
                "anchors": {"repo": "mbjorke/.gittan"},
            },
            {
                "source": "Cursor",
                "detail": "work",
                "anchors": {"repo": "mbjorke/project-alpha"},
            },
        ]
        self.assertEqual(unconfigured_repo_slugs_in_events(events, profiles), ["mbjorke/new-repo"])


class MapCommandFlowTests(unittest.TestCase):
    @patch("core.map_command.run_interactive_mapping_flow")
    @patch("core.map_command.build_mapping_review")
    @patch("core.map_command.maybe_run_interactive_anchor_mapping", return_value=True)
    @patch("core.report_service.run_timelog_report")
    def test_skips_repo_scan_by_default(
        self,
        report_mock,
        anchor_mock,
        review_mock,
        flow_mock,
    ) -> None:
        report_mock.return_value = SimpleNamespace(
            all_events=[],
            profiles=[{"name": "project-alpha", "match_terms": []}],
            config_path="/tmp/projects.json",
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock(return_value=None)
        console.status.return_value.__exit__ = MagicMock(return_value=False)

        options = SimpleNamespace(
            projects_config="/tmp/projects.json",
            date_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        anchors_applied, repo_applied, hints = run_map_command(
            console,
            options=options,
            projects_config="/tmp/projects.json",
            scan_repos=False,
        )

        self.assertTrue(anchors_applied)
        self.assertFalse(repo_applied)
        self.assertEqual(hints, [])
        review_mock.assert_not_called()
        flow_mock.assert_not_called()
        anchor_mock.assert_called_once()

    @patch("core.map_command.run_interactive_mapping_flow", return_value=1)
    @patch("core.map_command.build_mapping_review")
    @patch("core.map_command.maybe_run_interactive_anchor_mapping", return_value=False)
    @patch("core.report_service.run_timelog_report")
    def test_scan_repos_runs_full_review(
        self,
        report_mock,
        anchor_mock,
        review_mock,
        flow_mock,
    ) -> None:
        review_mock.return_value = MappingReview(new_projects=[MagicMock()], changes=[])
        report_mock.return_value = SimpleNamespace(
            all_events=[],
            profiles=[],
            config_path="/tmp/projects.json",
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock(return_value=None)
        console.status.return_value.__exit__ = MagicMock(return_value=False)

        options = SimpleNamespace(
            projects_config="/tmp/projects.json",
            date_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        _, repo_applied, _ = run_map_command(
            console,
            options=options,
            projects_config="/tmp/projects.json",
            scan_repos=True,
        )

        self.assertTrue(repo_applied)
        review_mock.assert_called_once()
        flow_mock.assert_called_once()
        anchor_mock.assert_called_once()


class MapExitMessageTests(unittest.TestCase):
    def test_success_message_when_anchor_mapped(self) -> None:
        text = map_exit_message(anchors_applied=True, repo_applied=False, had_repo_hints=False)
        self.assertIn("Re-run", text)

    def test_scan_repos_hint_when_repo_hints_skipped(self) -> None:
        text = map_exit_message(anchors_applied=False, repo_applied=False, had_repo_hints=True)
        self.assertIn("--scan-repos", text)

    def test_idle_message_when_nothing_to_do(self) -> None:
        text = map_exit_message(anchors_applied=False, repo_applied=False, had_repo_hints=False)
        self.assertIn("--scan-repos", text)


if __name__ == "__main__":
    unittest.main()
