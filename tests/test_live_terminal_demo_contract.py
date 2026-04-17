"""Tests for live terminal sandbox P0 allowlist contract."""

from __future__ import annotations

import unittest

from core.live_terminal.contract import (
    DEMO_SANDBOX_DENIED_MESSAGE,
    is_allowlisted_demo_command,
    normalize_demo_command_line,
    validate_demo_command,
)


class LiveTerminalDemoContractTests(unittest.TestCase):
    def test_allowed_exact(self):
        for cmd in (
            "gittan doctor",
            "gittan report --today --source-summary",
            "gittan report --today --format json",
            "gittan report --today --invoice-pdf",
            "help",
            "clear",
        ):
            with self.subTest(cmd=cmd):
                self.assertTrue(is_allowlisted_demo_command(cmd))

    def test_allowed_normalized_spacing_and_case(self):
        self.assertTrue(is_allowlisted_demo_command("  gittan   doctor  "))
        self.assertTrue(is_allowlisted_demo_command("GITTAN DOCTOR"))
        self.assertTrue(is_allowlisted_demo_command("Help"))

    def test_denied_unknown_and_injection(self):
        self.assertFalse(is_allowlisted_demo_command("gittan report --today"))
        self.assertFalse(is_allowlisted_demo_command("gittan doctor --help"))
        self.assertFalse(is_allowlisted_demo_command("gittan doctor; rm -rf /"))
        self.assertFalse(is_allowlisted_demo_command(""))
        self.assertFalse(is_allowlisted_demo_command("ls"))

    def test_validate_returns_denial_copy(self):
        ok, msg = validate_demo_command("gittan doctor")
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        ok, msg = validate_demo_command("evil")
        self.assertFalse(ok)
        self.assertEqual(msg, DEMO_SANDBOX_DENIED_MESSAGE)

    def test_normalize_stable(self):
        self.assertEqual(normalize_demo_command_line("  a  b\tc  "), "a b c")


if __name__ == "__main__":
    unittest.main()
