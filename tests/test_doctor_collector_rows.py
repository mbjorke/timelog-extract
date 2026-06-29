"""Tests for SOURCE_ORDER-aligned doctor collector rows."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.doctor_collector_rows import add_collector_doctor_rows
from core.doctor_table_checks import DoctorCheckStyle

_MARKUP_RE = re.compile(r"\[/??[^\]]+\]")


def _plain(text: str) -> str:
    return _MARKUP_RE.sub("", text)


def _capture_rows(home: Path) -> list[tuple[str, str, str]]:
    captured: list[tuple[str, str, str]] = []

    class _CaptureTable:
        def add_row(self, source: str, status: str, detail: str) -> None:
            captured.append((source, status, detail))

    style = DoctorCheckStyle(
        ok_icon="OK",
        warn_icon="WARN",
        fail_icon="FAIL",
        style_muted="dim",
    )
    codec_blocked: list[str] = []
    add_collector_doctor_rows(_CaptureTable(), home, style, codec_blocked=codec_blocked)
    return captured


class DoctorCollectorRowsTests(unittest.TestCase):
    def test_ai_ide_rows_precede_passive_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            rows = _capture_rows(home)
            labels = [label for label, _, _ in rows]

            self.assertLess(labels.index("Claude Code CLI"), labels.index("Apple Mail"))
            self.assertLess(labels.index("Zed"), labels.index("Apple Mail"))
            self.assertLess(labels.index("Apple Mail"), labels.index("Screen Time"))
            self.assertLess(labels.index("Chrome"), labels.index("Screen Time"))

    def test_missing_optional_sources_read_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = {
                label: _plain(detail)
                for label, _, detail in _capture_rows(Path(tmp))
            }
            self.assertEqual(rows["Zed"], "Not installed")
            self.assertEqual(rows["Codex IDE"], "Not installed")
            self.assertEqual(rows["Gemini CLI"], "Not installed")
            self.assertEqual(rows["Claude Desktop"], "Not installed")

    def test_web_url_sources_require_chrome_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = {
                label: _plain(detail)
                for label, _, detail in _capture_rows(Path(tmp))
            }
            self.assertEqual(rows["Claude.ai (web)"], "Requires Chrome History")
            self.assertEqual(rows["Gemini (web)"], "Requires Chrome History")

    def test_zed_row_probe_when_db_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db_path = home / "threads.db"
            db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)

            with patch("core.doctor_collector_rows._find_zed_db", return_value=db_path):
                with patch("core.doctor_collector_rows.doctor_probe_sqlite") as probe:
                    _capture_rows(home)
                    probe.assert_called_once()
                    args = probe.call_args[0]
                    self.assertEqual(args[2], "Zed")

    def test_new_sources_appear_in_doctor_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            labels = [label for label, _, _ in _capture_rows(Path(tmp))]
            for expected in (
                "Claude Desktop",
                "Cursor (agent)",
                "Codex IDE",
                "Gemini CLI",
                "Zed",
            ):
                self.assertIn(expected, labels)


if __name__ == "__main__":
    unittest.main()
