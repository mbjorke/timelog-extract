"""Tests for post-report follow-ups (nudges + mapping prompt)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from core.report_postamble import run_post_report_followups, status_anchor_warn_line


class ReportPostambleTests(unittest.TestCase):
    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.prepare_mapping_review_after_report")
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    @patch(
        "core.report_postamble.unanchored_anchors_for_report",
        return_value=[{"kind": "dir", "value": "timelog-extract", "hits": 30}],
    )
    def test_prints_static_anchor_nudge_after_spinner_scan(
        self,
        _anchors_for_report,
        _wants_mapping,
        _gap,
        _prepare,
        _mapping,
        _anchors,
    ):
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace(quiet=False, output_format="terminal"))
        with patch("core.report_postamble._wants_status", return_value=True):
            run_post_report_followups(console, report)
        _anchors.assert_called_once_with(
            report, anchors=[{"kind": "dir", "value": "timelog-extract", "hits": 30}]
        )
        self.assertEqual(console.print.call_args_list[-1], call("anchor-nudge"))

    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.prepare_mapping_review_after_report")
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    def test_shows_status_for_mapping_then_anchors(
        self,
        _wants_mapping,
        _gap,
        _prepare,
        _mapping,
        _anchors,
    ):
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace(quiet=False, output_format="terminal"))
        with patch("core.report_postamble._wants_status", return_value=True):
            run_post_report_followups(console, report)
        self.assertEqual(console.status.call_count, 2)

    @patch("core.report_postamble.build_unanchored_anchors_nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=True)
    @patch("core.report_postamble.prepare_mapping_review_after_report")
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value="gap-nudge")
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    def test_skips_anchor_scan_after_interactive_mapping(
        self,
        _wants_mapping,
        _gap,
        _prepare,
        _mapping,
        anchors_mock,
    ):
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace(quiet=False, output_format="terminal"))
        with patch("core.report_postamble._wants_status", return_value=True):
            run_post_report_followups(console, report)
        anchors_mock.assert_not_called()
        console.print.assert_called_once_with("gap-nudge")
        self.assertEqual(console.status.call_count, 1)

    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.prepare_mapping_review_after_report")
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    def test_no_status_when_quiet(
        self,
        _gap,
        _prepare,
        _mapping,
        _anchors,
    ):
        console = MagicMock()
        report = SimpleNamespace(args=SimpleNamespace(quiet=True, output_format="terminal"))
        with patch("core.report_postamble.should_prompt", return_value=True):
            run_post_report_followups(console, report)
        console.status.assert_not_called()
        _mapping.assert_not_called()
        self.assertEqual(console.print.call_args_list[-1], call("anchor-nudge"))

    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.prepare_mapping_review_after_report")
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    @patch("core.report_postamble.should_prompt", return_value=False)
    def test_no_status_when_not_tty(
        self,
        _should_prompt,
        _gap,
        _prepare,
        _mapping,
        _anchors,
    ):
        console = MagicMock()
        report = SimpleNamespace(args=SimpleNamespace(quiet=False, output_format="terminal"))
        run_post_report_followups(console, report)
        console.status.assert_not_called()
        _mapping.assert_not_called()
        self.assertEqual(console.print.call_args_list[-1], call("anchor-nudge"))

    @patch("core.report_nudges.unanchored_anchors_for_report", return_value=["/tmp/repo"])
    @patch("core.anchor_nudge.status_anchor_line", return_value="warn-line")
    @patch("core.report_postamble.should_prompt", return_value=True)
    def test_status_anchor_warn_line_shows_spinner_when_quiet_ignored(
        self,
        _should_prompt,
        _status_line,
        _anchors,
    ):
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace(quiet=True, output_format="terminal"))
        line = status_anchor_warn_line(report, console=console, ignore_quiet=True)
        self.assertEqual(line, "warn-line")
        console.status.assert_called_once()


class PeriodLabelTests(unittest.TestCase):
    def test_period_label_formats_datetime_as_date_only(self):
        from datetime import datetime

        from outputs.terminal_report_sections import period_label

        args = SimpleNamespace(
            date_from=datetime(2026, 5, 1, 0, 0, 0),
            date_to=datetime(2026, 5, 30, 23, 59, 59),
        )
        self.assertEqual(period_label(args), "2026-05-01 to 2026-05-30")

    def test_period_label_single_day(self):
        from datetime import date

        from outputs.terminal_report_sections import period_label

        args = SimpleNamespace(date_from=date(2026, 6, 25), date_to=date(2026, 6, 25))
        self.assertEqual(period_label(args), "2026-06-25")


if __name__ == "__main__":
    unittest.main()
