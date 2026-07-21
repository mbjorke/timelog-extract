"""Tests for Apple Mail collector registry logic with on/auto/off modes and mail_root presence."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.collector_registry import build_collector_specs


class CollectorRegistryMailTests(unittest.TestCase):
    def _get_mail_spec(self, mail_source: str, mail_root_exists: bool, mail_msg: str = "mail unavailable"):
        args = type(
            "Args",
            (),
            {
                "chrome_source": "off",
                "mail_source": mail_source,
                "github_source": "off",
                "github_user": None,
                "chrome_collapse_minutes": 12,
                "toggl_source": "off",
                "toggl_api_token": None,
                "calendar_source": "off",
                "email": "test@example.com",
            }
        )()

        mail_root = Path("/tmp/mock_mail") if mail_root_exists else None

        specs = build_collector_specs(
            args,
            Path("TIMELOG.md"),
            chrome_history_exists=False,
            lovable_desktop_history_exists=False,
            mail_root=mail_root,
            mail_msg=mail_msg,
            collect_claude_code=lambda *_: [],
            collect_claude_desktop=lambda *_: [],
            collect_claude_desktop_code=lambda *_: [],
            collect_claude_ai_urls=lambda *_: [],
            collect_gemini_web_urls=lambda *_: [],
            collect_chrome=lambda *_: [],
            collect_lovable_desktop=lambda *_: [],
            collect_gemini_cli=lambda *_: [],
            collect_copilot_cli=lambda *_: [],
            collect_cursor=lambda *_: [],
            collect_antigravity=lambda *_: [],
            collect_windsurf=lambda *_: [],
            collect_cursor_checkpoints=lambda *_: [],
            collect_codex_ide=lambda *_: [],
            collect_apple_mail=lambda *_: [],
            collect_worklog=lambda *_: [],
            collect_github=lambda *_: [],
            collect_toggl=lambda *_: [],
            collect_calendar=lambda *_: [],
            collect_zed=lambda *_: [],
            collect_conductor=lambda *_: [],
        )
        return next((spec for spec in specs if spec.name == "Apple Mail"), None)

    def test_mail_source_off(self):
        spec = self._get_mail_spec(mail_source="off", mail_root_exists=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertFalse(spec.enabled)
        self.assertEqual(spec.reason, "Consent/source setting disabled")

        spec_missing = self._get_mail_spec(mail_source="off", mail_root_exists=False)
        self.assertIsNotNone(spec_missing)
        assert spec_missing is not None
        self.assertFalse(spec_missing.enabled)
        self.assertEqual(spec_missing.reason, "Consent/source setting disabled")

    def test_mail_source_on_with_root(self):
        spec = self._get_mail_spec(mail_source="on", mail_root_exists=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertTrue(spec.enabled)
        self.assertIsNone(spec.reason)

    def test_mail_source_on_without_root(self):
        spec = self._get_mail_spec(mail_source="on", mail_root_exists=False, mail_msg="~/Library/Mail not found.")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertTrue(spec.enabled)
        self.assertEqual(spec.reason, "~/Library/Mail not found.")

    def test_mail_source_auto_with_root(self):
        spec = self._get_mail_spec(mail_source="auto", mail_root_exists=True)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertTrue(spec.enabled)
        self.assertIsNone(spec.reason)

    def test_mail_source_auto_without_root(self):
        spec = self._get_mail_spec(mail_source="auto", mail_root_exists=False, mail_msg="~/Library/Mail not found.")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertFalse(spec.enabled)
        self.assertEqual(spec.reason, "~/Library/Mail not found.")


if __name__ == "__main__":
    unittest.main()
