"""Tests for backward-compatible wrapper modules updated in this PR.

Verifies that each wrapper re-exports the expected public symbols explicitly
(previously star-imports were replaced with explicit named imports + __all__).
"""

from __future__ import annotations

import unittest


class LiveTerminalDemoContractWrapperTests(unittest.TestCase):
    """core.live_terminal_demo_contract is a backward-compat wrapper for core.live_terminal.contract."""

    def test_demo_sandbox_denied_message_importable(self):
        from core.live_terminal_demo_contract import DEMO_SANDBOX_DENIED_MESSAGE
        self.assertIsInstance(DEMO_SANDBOX_DENIED_MESSAGE, str)
        self.assertGreater(len(DEMO_SANDBOX_DENIED_MESSAGE), 0)

    def test_normalize_demo_command_line_importable_and_works(self):
        from core.live_terminal_demo_contract import normalize_demo_command_line
        result = normalize_demo_command_line("  GITTAN  DOCTOR  ")
        self.assertEqual(result, "gittan doctor")

    def test_is_allowlisted_demo_command_importable_and_works(self):
        from core.live_terminal_demo_contract import is_allowlisted_demo_command
        self.assertTrue(is_allowlisted_demo_command("help"))
        self.assertFalse(is_allowlisted_demo_command("rm -rf /"))

    def test_validate_demo_command_importable_and_works(self):
        from core.live_terminal_demo_contract import validate_demo_command
        ok, msg = validate_demo_command("clear")
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        ok, msg = validate_demo_command("evil")
        self.assertFalse(ok)
        self.assertGreater(len(msg), 0)

    def test_module_all_lists_expected_symbols(self):
        import core.live_terminal_demo_contract as mod
        expected = {
            "DEMO_SANDBOX_DENIED_MESSAGE",
            "normalize_demo_command_line",
            "is_allowlisted_demo_command",
            "validate_demo_command",
        }
        self.assertEqual(set(mod.__all__), expected)

    def test_wrapper_is_same_object_as_canonical(self):
        """The wrapper must re-export the exact same objects, not copies."""
        from core.live_terminal_demo_contract import DEMO_SANDBOX_DENIED_MESSAGE as compat_msg
        from core.live_terminal.contract import DEMO_SANDBOX_DENIED_MESSAGE as canonical_msg
        self.assertIs(compat_msg, canonical_msg)


class LiveTerminalDemoHttpWrapperTests(unittest.TestCase):
    """core.live_terminal_demo_http is a backward-compat wrapper for core.live_terminal.http."""

    def test_make_demo_handler_importable(self):
        from core.live_terminal_demo_http import make_demo_handler
        self.assertTrue(callable(make_demo_handler))

    def test_serve_demo_importable(self):
        from core.live_terminal_demo_http import serve_demo
        self.assertTrue(callable(serve_demo))

    def test_module_all_lists_expected_symbols(self):
        import core.live_terminal_demo_http as mod
        self.assertEqual(set(mod.__all__), {"make_demo_handler", "serve_demo"})

    def test_wrapper_is_same_object_as_canonical(self):
        from core.live_terminal_demo_http import make_demo_handler as compat_fn
        from core.live_terminal.http import make_demo_handler as canonical_fn
        self.assertIs(compat_fn, canonical_fn)


class ScreenTimeGapAnalysisWrapperTests(unittest.TestCase):
    """core.screen_time_gap_analysis is a backward-compat wrapper for core.calibration.screen_time_gap."""

    def test_day_gap_importable(self):
        from core.screen_time_gap_analysis import DayGap
        self.assertIsNotNone(DayGap)

    def test_analyze_screen_time_gaps_importable_and_callable(self):
        from core.screen_time_gap_analysis import analyze_screen_time_gaps
        self.assertTrue(callable(analyze_screen_time_gaps))

    def test_module_all_lists_expected_symbols(self):
        import core.screen_time_gap_analysis as mod
        self.assertEqual(set(mod.__all__), {"DayGap", "analyze_screen_time_gaps"})

    def test_wrapper_is_same_object_as_canonical(self):
        from core.screen_time_gap_analysis import analyze_screen_time_gaps as compat_fn
        from core.calibration.screen_time_gap import analyze_screen_time_gaps as canonical_fn
        self.assertIs(compat_fn, canonical_fn)

    def test_day_gap_is_same_class_as_canonical(self):
        from core.screen_time_gap_analysis import DayGap as compat_cls
        from core.calibration.screen_time_gap import DayGap as canonical_cls
        self.assertIs(compat_cls, canonical_cls)


class LiveTerminalContractAllTests(unittest.TestCase):
    """core.live_terminal.contract gained __all__ in this PR."""

    def test_all_defined(self):
        import core.live_terminal.contract as mod
        self.assertTrue(hasattr(mod, "__all__"))
        self.assertIsInstance(mod.__all__, list)

    def test_all_contains_expected_symbols(self):
        import core.live_terminal.contract as mod
        expected = {
            "DEMO_SANDBOX_DENIED_MESSAGE",
            "normalize_demo_command_line",
            "is_allowlisted_demo_command",
            "validate_demo_command",
        }
        self.assertEqual(set(mod.__all__), expected)


class LiveTerminalHttpAllTests(unittest.TestCase):
    """core.live_terminal.http gained __all__ in this PR."""

    def test_all_defined(self):
        import core.live_terminal.http as mod
        self.assertTrue(hasattr(mod, "__all__"))

    def test_all_contains_expected_symbols(self):
        import core.live_terminal.http as mod
        self.assertEqual(set(mod.__all__), {"make_demo_handler", "serve_demo"})


if __name__ == "__main__":
    unittest.main()