"""Tests for Toggl source auto-detection and collector registry wiring."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from collectors import toggl as tg
from core.collector_registry import build_collector_specs


class TogglSourceTests(unittest.TestCase):
    def test_toggl_source_auto_without_token_is_disabled(self):
        class Args:
            toggl_source = "auto"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": ""}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertFalse(enabled)
        self.assertIsNotNone(reason)
        self.assertIn("TOGGL_API_TOKEN", reason or "")

    def test_toggl_source_auto_with_token_is_enabled(self):
        class Args:
            toggl_source = "auto"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "token-123"}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertTrue(enabled)
        self.assertIsNone(reason)

    def test_collector_registry_includes_toggl_status(self):
        class Args:
            chrome_source = "on"
            mail_source = "auto"
            github_source = "auto"
            github_user = None
            chrome_collapse_minutes = 12
            toggl_source = "auto"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "token-123"}, clear=False):
            specs = build_collector_specs(
                Args(),
                Path("TIMELOG.md"),
                chrome_history_exists=False,
                lovable_desktop_history_exists=False,
                mail_root=None,
                mail_msg="mail unavailable",
                collect_claude_code=lambda *_: [],
                collect_claude_desktop=lambda *_: [],
                collect_claude_ai_urls=lambda *_: [],
                collect_gemini_web_urls=lambda *_: [],
                collect_chrome=lambda *_: [],
                collect_lovable_desktop=lambda *_: [],
                collect_gemini_cli=lambda *_: [],
                collect_copilot_cli=lambda *_: [],
                collect_cursor=lambda *_: [],
                collect_cursor_checkpoints=lambda *_: [],
                collect_codex_ide=lambda *_: [],
                collect_apple_mail=lambda *_: [],
                collect_worklog=lambda *_: [],
                collect_github=lambda *_: [],
                collect_toggl=lambda *_: [],
            )
        toggl = next((spec for spec in specs if spec.name == "Toggl"), None)
        self.assertIsNotNone(toggl)
        assert toggl is not None
        self.assertTrue(toggl.enabled)
        self.assertIsNone(toggl.reason)


    def test_toggl_source_invalid_mode_is_rejected(self):
        """New in PR: invalid mode string returns (False, descriptive error)."""
        class Args:
            toggl_source = "bogus"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "token-123"}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertFalse(enabled)
        self.assertIsNotNone(reason)
        self.assertIn("bogus", reason or "")
        self.assertIn("auto/on/off", reason or "")

    def test_toggl_source_off_is_disabled_even_with_token(self):
        """Mode=off should always return disabled regardless of token presence."""
        class Args:
            toggl_source = "off"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "token-123"}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertFalse(enabled)
        self.assertIsNotNone(reason)
        self.assertIn("off", reason or "")

    def test_toggl_source_on_without_token_is_disabled(self):
        """Mode=on without a token returns disabled with clear message."""
        class Args:
            toggl_source = "on"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": ""}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertFalse(enabled)
        self.assertIsNotNone(reason)
        self.assertIn("TOGGL_API_TOKEN", reason or "")

    def test_toggl_source_on_with_token_is_enabled(self):
        """Mode=on with token present returns enabled."""
        class Args:
            toggl_source = "on"
            toggl_api_token = None

        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "my-token"}, clear=False):
            enabled, reason = tg.toggl_source_enabled(Args())
        self.assertTrue(enabled)
        self.assertIsNone(reason)

    def test_toggl_source_invalid_mode_error_message_format(self):
        """Error message for invalid mode includes mode value and expectation hint."""
        class Args:
            toggl_source = "maybe"
            toggl_api_token = None

        enabled, reason = tg.toggl_source_enabled(Args())
        self.assertFalse(enabled)
        self.assertIn("maybe", reason or "")
        self.assertIn("expected", (reason or "").lower())

    def test_collect_workspace_events_returns_empty_list(self):
        """collect_workspace_events is a placeholder that returns no events."""
        result = tg.collect_workspace_events()
        self.assertEqual(result, [])
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()