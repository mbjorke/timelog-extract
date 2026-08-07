"""Tests for scripts/changelog_section.py (GitHub Release notes helper)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "changelog_section.py"
    spec = importlib.util.spec_from_file_location("changelog_section", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_CHANGELOG = """# Changelog

## Unreleased

- pending

## 0.4.0 - 2026-08-07

- Sources: **VS Code**
- Fix: something

## 0.3.1 - 2026-07-04

- Packaging: Python floor

## 1.0.0 - Draft (CLI-first)

- draft notes (not a shippable X.Y.Z match for extractor heading rules)
"""


class TestChangelogSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_module()

    def test_extracts_body_without_heading(self) -> None:
        body = self.mod.extract_section(_CHANGELOG, "0.4.0")
        self.assertIn("Sources: **VS Code**", body)
        self.assertIn("Fix: something", body)
        self.assertNotIn("## 0.4.0", body)
        self.assertNotIn("0.3.1", body)

    def test_missing_version(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.extract_section(_CHANGELOG, "9.9.9")

    def test_rejects_draft_heading(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.extract_section(_CHANGELOG, "1.0.0")

    def test_cli_writes_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(_CHANGELOG, encoding="utf-8")
            code = self.mod.main(["0.3.1", "--file", str(path)])
            self.assertEqual(code, 0)

    def test_cli_rejects_bad_version(self) -> None:
        code = self.mod.main(["v0.4.0"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
