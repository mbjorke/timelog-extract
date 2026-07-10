"""Legacy top-level report flags redirect to the `report` subcommand (GH-123).

`gittan --today` predates the `report` subcommand and must not dead-end with
`No such option: --today`; it is rewritten to `gittan report --today`.
"""

from __future__ import annotations

import unittest

from core.cli import redirect_legacy_report_argv


class LegacyReportRedirectTests(unittest.TestCase):
    def test_bare_today_flag_gets_report_inserted(self):
        argv = ["gittan", "--today"]
        self.assertEqual(redirect_legacy_report_argv(argv), ["gittan", "report", "--today"])

    def test_legacy_report_flags_are_preserved_after_report(self):
        argv = ["gittan", "--today", "--screen-time", "off", "--source-summary"]
        self.assertEqual(
            redirect_legacy_report_argv(argv),
            ["gittan", "report", "--today", "--screen-time", "off", "--source-summary"],
        )

    def test_explicit_report_subcommand_is_unchanged(self):
        argv = ["gittan", "report", "--today"]
        self.assertEqual(redirect_legacy_report_argv(argv), argv)

    def test_other_subcommands_are_unchanged(self):
        for sub in ("doctor", "setup", "map", "review"):
            with self.subTest(sub=sub):
                argv = ["gittan", sub]
                self.assertEqual(redirect_legacy_report_argv(argv), argv)

    def test_top_level_only_options_are_unchanged(self):
        for opt in ("--help", "-h", "--version", "-V", "--install-completion", "--show-completion"):
            with self.subTest(opt=opt):
                argv = ["gittan", opt]
                self.assertEqual(redirect_legacy_report_argv(argv), argv)

    def test_bare_invocation_is_unchanged(self):
        argv = ["gittan"]
        self.assertEqual(redirect_legacy_report_argv(argv), argv)

    def test_redirect_does_not_mutate_input(self):
        argv = ["gittan", "--today"]
        redirect_legacy_report_argv(argv)
        self.assertEqual(argv, ["gittan", "--today"])


if __name__ == "__main__":
    unittest.main()
