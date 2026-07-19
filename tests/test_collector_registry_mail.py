"""Apple Mail enablement states in build_collector_specs."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from core.collector_registry import build_collector_specs


def _specs(*, mail_source: str, mail_root: Path | None, mail_msg: str = "mail unavailable") -> Any:
    class Args:
        chrome_source = "on"
        chrome_collapse_minutes = 12
        github_source = "off"
        github_user = None
        toggl_source = "off"
        toggl_api_token = None
        calendar_source = "off"
        email = None

    Args.mail_source = mail_source  # type: ignore[attr-defined]

    return build_collector_specs(
        Args(),
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


def _mail_spec(mail_source: str, mail_root: Path | None, mail_msg: str = "mail unavailable"):
    specs = _specs(mail_source=mail_source, mail_root=mail_root, mail_msg=mail_msg)
    mail = next(spec for spec in specs if spec.name == "Apple Mail")
    return mail


class CollectorRegistryMailTests(unittest.TestCase):
    def test_auto_without_mail_root_disables_with_specific_reason(self):
        mail = _mail_spec("auto", None, mail_msg="No versioned Mail directory")
        self.assertFalse(mail.enabled)
        self.assertEqual(mail.reason, "No versioned Mail directory")

    def test_auto_with_mail_root_enables(self):
        mail = _mail_spec("auto", Path("/tmp/Mail"))
        self.assertTrue(mail.enabled)
        self.assertIsNone(mail.reason)

    def test_on_without_mail_root_stays_enabled_with_specific_reason(self):
        mail = _mail_spec("on", None, mail_msg="access denied")
        self.assertTrue(mail.enabled)
        self.assertEqual(mail.reason, "access denied")

    def test_on_with_mail_root_enables(self):
        mail = _mail_spec("on", Path("/tmp/Mail"))
        self.assertTrue(mail.enabled)
        self.assertIsNone(mail.reason)

    def test_off_uses_consent_reason(self):
        mail = _mail_spec("off", Path("/tmp/Mail"))
        self.assertFalse(mail.enabled)
        self.assertEqual(mail.reason, "Consent/source setting disabled")


if __name__ == "__main__":
    unittest.main()
