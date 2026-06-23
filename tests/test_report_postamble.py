"""Tests for post-report follow-ups (nudges + mapping prompt)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.report_postamble import run_post_report_followups


class ReportPostambleTests(unittest.TestCase):
    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    @patch("core.report_postamble._show_status_spinner", return_value=True)
    @patch("core.report_postamble.Console")
    def test_shows_status_for_mapping_then_anchors(
        self,
        console_cls,
        _show_status,
        _wants_mapping,
        _gap,
        _mapping,
        _anchors,
    ):
        console_cls.return_value.status.return_value.__enter__ = MagicMock()
        console_cls.return_value.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace())
        with patch("builtins.print") as print_mock:
            run_post_report_followups(report)
        self.assertEqual(console_cls.return_value.status.call_count, 2)
        print_mock.assert_called_once_with("anchor-nudge")

    @patch("core.report_postamble.build_unanchored_anchors_nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=True)
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value="gap-nudge")
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    @patch("core.report_postamble._show_status_spinner", return_value=True)
    @patch("core.report_postamble.Console")
    def test_skips_anchor_scan_after_interactive_mapping(
        self,
        console_cls,
        _show_status,
        _wants_mapping,
        _gap,
        _mapping,
        anchors_mock,
    ):
        console_cls.return_value.status.return_value.__enter__ = MagicMock()
        console_cls.return_value.status.return_value.__exit__ = MagicMock(return_value=False)
        report = SimpleNamespace(args=SimpleNamespace())
        with patch("builtins.print") as print_mock:
            run_post_report_followups(report)
        anchors_mock.assert_not_called()
        print_mock.assert_called_once_with("gap-nudge")
        self.assertEqual(console_cls.return_value.status.call_count, 1)

    @patch("core.report_postamble.build_unanchored_anchors_nudge", return_value="anchor-nudge")
    @patch("core.report_postamble.maybe_run_mapping_assistant_after_report", return_value=False)
    @patch("core.report_postamble.build_unexplained_gap_nudge", return_value=None)
    @patch("core.report_postamble._wants_mapping_prompt", return_value=True)
    @patch("core.report_postamble._show_status_spinner", return_value=False)
    @patch("core.report_postamble.Console")
    def test_quiet_skips_status_spinner(self, console_cls, _show, _wants, _gap, _map, _anchors):
        report = SimpleNamespace(args=SimpleNamespace(quiet=True))
        with patch("builtins.print") as print_mock:
            run_post_report_followups(report)
        console_cls.return_value.status.assert_not_called()
        print_mock.assert_called_once_with("anchor-nudge")


if __name__ == "__main__":
    unittest.main()
