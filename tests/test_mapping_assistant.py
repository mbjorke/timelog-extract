from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.mapping_assistant import (
    apply_mapping_changes,
    collect_actionable_mapping_signals,
    maybe_run_mapping_assistant_after_report,
    prepare_mapping_review_after_report,
    run_interactive_mapping_flow,
    run_setup_evidence_mapping,
)


class MappingAssistantTests(unittest.TestCase):
    def test_collect_actionable_mapping_signals_skips_labels_and_hosts(self):
        report = SimpleNamespace(
            profiles=[],
            all_events=[
                {
                    "source": "Cursor",
                    "detail": "Freelance bridge dashboard development",
                    "anchors": {"label": "freelance bridge dashboard development"},
                    "project": "Uncategorized",
                },
                {
                    "source": "Lovable (desktop)",
                    "detail": "storage signal — https://810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com/",
                    "project": "Uncategorized",
                },
            ],
            included_events=[],
            dt_from=None,
            dt_to=None,
        )
        with patch(
            "core.mapping_assistant.discover_unmapped_git_signals",
            return_value=[{"kind": "git_slug", "value": "org/example", "hits": 2}],
        ) as discover_mock:
            signals = collect_actionable_mapping_signals(report, include_workspace_repos=True)
        discover_mock.assert_called_once()
        self.assertEqual(signals[0]["kind"], "git_slug")

    def test_collect_actionable_mapping_signals_empty_without_workspace_scan(self):
        report = SimpleNamespace(profiles=[], all_events=[], included_events=[], dt_from=None, dt_to=None)
        self.assertEqual(collect_actionable_mapping_signals(report), [])

    def test_maybe_run_skips_when_no_map_prompt(self):
        report = SimpleNamespace(
            args=SimpleNamespace(map_prompt=False, output_format="terminal"),
            profiles=[],
            all_events=[],
            included_events=[],
        )
        self.assertFalse(maybe_run_mapping_assistant_after_report(MagicMock(), report))

    @patch("core.mapping_assistant.should_prompt", return_value=True)
    @patch("core.mapping_review.build_mapping_review")
    def test_maybe_run_skips_workspace_git_signal_scan(self, review_mock, _tty_mock):
        review_mock.return_value = SimpleNamespace(change_count=lambda: 0)
        report = SimpleNamespace(
            args=SimpleNamespace(map_prompt=True, output_format="terminal"),
            profiles=[],
            all_events=[],
            included_events=[],
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 22, tzinfo=timezone.utc),
        )
        with patch("core.mapping_assistant.collect_actionable_mapping_signals") as collect_mock:
            self.assertFalse(
                maybe_run_mapping_assistant_after_report(MagicMock(), report, fast_post_report=True)
            )
        collect_mock.assert_not_called()
        review_mock.assert_called_once()
        self.assertFalse(review_mock.call_args.kwargs.get("gh_discovery", True))
        self.assertEqual(review_mock.call_args.kwargs.get("slug_bindings"), {})

    def test_prepare_fast_mode_skips_local_and_gh_discovery(self):
        report = SimpleNamespace(
            profiles=[],
            all_events=[{"source": "GitHub", "detail": "org/example"}],
            included_events=[],
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 22, tzinfo=timezone.utc),
        )
        with patch("core.mapping_assistant.collect_actionable_mapping_signals") as collect_mock:
            with patch("core.mapping_review.index_local_slug_bindings") as index_mock:
                with patch("core.mapping_review.collect_gh_repo_list_data") as gh_mock:
                    prepare_mapping_review_after_report(report, fast_post_report=True)
        collect_mock.assert_not_called()
        index_mock.assert_not_called()
        gh_mock.assert_not_called()

    @patch("core.mapping_review.build_mapping_review")
    def test_prepare_default_mode_uses_full_discovery(self, review_mock):
        review_mock.return_value = SimpleNamespace(change_count=lambda: 0)
        report = SimpleNamespace(
            profiles=[],
            all_events=[],
            included_events=[],
            dt_from=None,
            dt_to=None,
        )
        with patch(
            "core.mapping_assistant.collect_actionable_mapping_signals",
            return_value=[{"kind": "git_slug", "value": "org/example", "hits": 1}],
        ) as collect_mock:
            prepare_mapping_review_after_report(report, fast_post_report=False)
        collect_mock.assert_called_once_with(report, include_workspace_repos=True)
        review_mock.assert_called_once()
        self.assertNotIn("gh_discovery", review_mock.call_args.kwargs)

    @patch("core.mapping_assistant.should_prompt", return_value=True)
    @patch("core.mapping_review.build_mapping_review")
    @patch("questionary.confirm")
    def test_gate_confirm_defaults_yes(self, confirm_mock, review_mock, _tty_mock):
        review_mock.return_value = SimpleNamespace(change_count=lambda: 1)
        confirm_mock.return_value.ask.return_value = False
        report = SimpleNamespace(
            args=SimpleNamespace(map_prompt=True, output_format="terminal"),
            profiles=[],
            config_path="/tmp/timelog_projects.json",
            all_events=[],
            included_events=[],
            dt_from=None,
            dt_to=None,
        )
        console = MagicMock()
        maybe_run_mapping_assistant_after_report(console, report)
        confirm_mock.assert_called_once()
        self.assertTrue(confirm_mock.call_args.kwargs.get("default"))

    @patch("core.report_service.run_timelog_report")
    @patch("core.cli_report_status_helpers.build_report_options")
    @patch(
        "core.cli_report_status_helpers.resolve_timeframe_args",
        return_value=("2026-06-04", "2026-06-11", False, False, False, True, False, False),
    )
    def test_setup_evidence_mapping_dry_run_lists_signals(self, _tf, _opts, report_mock):
        from pathlib import Path

        report_mock.return_value = SimpleNamespace(
            profiles=[{"name": "project-alpha", "match_terms": []}],
            all_events=[],
            included_events=[],
            dt_from=None,
            dt_to=None,
        )
        with patch("core.mapping_review.build_mapping_review") as review_mock:
            review_mock.return_value = SimpleNamespace(change_count=lambda: 1, new_projects=[], changes=[])
            console = MagicMock()
            applied = run_setup_evidence_mapping(
                console,
                config_path=Path("/tmp/timelog_projects.json"),
                dry_run=True,
            )
        self.assertEqual(applied, 0)
        console.print.assert_called()

    def test_apply_mapping_changes_accepts_four_tuple_additions(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(json.dumps({"projects": []}), encoding="utf-8")
            console = MagicMock()
            count = apply_mapping_changes(
                console,
                [
                    (
                        "landsbanken-faq-helper",
                        "match_terms",
                        "mbjorke/landsbanken-faq-helper",
                        "Ålandsbanken Contact Center",
                        "Ålandsbanken Chatbot",
                    ),
                    ("landsbanken-faq-helper", "match_terms", "landsbanken-faq-helper"),
                ],
                [],
                str(cfg),
            )
            self.assertEqual(count, 2)
            project = json.loads(cfg.read_text(encoding="utf-8"))["projects"][0]
            self.assertEqual(project["name"], "landsbanken-faq-helper")
            self.assertEqual(project["customer"], "Ålandsbanken Contact Center")
            self.assertEqual(project["invoice_title"], "Ålandsbanken Chatbot")
            console.print.assert_any_call(
                "[green]Mapped 2 signal(s): mbjorke/landsbanken-faq-helper→landsbanken-faq-helper, "
                "landsbanken-faq-helper→landsbanken-faq-helper[/green]"
            )

    @patch("core.mapping_review.run_batch_mapping_review", return_value=0)
    @patch("core.mapping_review.build_mapping_review")
    def test_interactive_flow_uses_single_batch_gate(self, review_mock, batch_mock):
        review_mock.return_value = SimpleNamespace(change_count=lambda: 1)
        run_interactive_mapping_flow(
            MagicMock(),
            [],
            [{"name": "project-alpha", "match_terms": []}],
            "/tmp/timelog_projects.json",
            events=[],
        )
        batch_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
