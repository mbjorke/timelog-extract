from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from collectors.vscode_fork import enrich_ide_collector_versions, read_ide_version


class ReadIdeVersionTests(unittest.TestCase):
    def _write_product_json(self, base_dir: Path, payload: object) -> None:
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "product.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_returns_version_from_valid_product_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Cursor"
            self._write_product_json(base, {"version": "1.2.3"})
            self.assertEqual(read_ide_version(base), "1.2.3")

    def test_missing_product_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Cursor"
            base.mkdir()
            self.assertIsNone(read_ide_version(base))

    def test_malformed_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Cursor"
            base.mkdir()
            (base / "product.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(read_ide_version(base))

    def test_missing_version_field_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Cursor"
            self._write_product_json(base, {"nameShort": "Cursor"})
            self.assertIsNone(read_ide_version(base))

    def test_empty_version_string_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Cursor"
            self._write_product_json(base, {"version": "   "})
            self.assertIsNone(read_ide_version(base))


class EnrichIdeCollectorVersionsTests(unittest.TestCase):
    def _cursor_support(self, home: Path) -> Path:
        return home / "Library" / "Application Support" / "Cursor"

    def test_adds_cursor_version_when_product_json_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            support = self._cursor_support(home)
            support.mkdir(parents=True)
            (support / "product.json").write_text(
                json.dumps({"version": "0.42.3"}),
                encoding="utf-8",
            )
            status = {"Cursor": {"enabled": True, "reason": "", "events": 0}}
            enrich_ide_collector_versions(status, home)
            self.assertEqual(status["Cursor"]["version"], "0.42.3")

    def test_omits_version_when_product_json_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            status = {"Cursor": {"enabled": True, "reason": "", "events": 0}}
            enrich_ide_collector_versions(status, home)
            self.assertNotIn("version", status["Cursor"])

    def test_enriches_disabled_collector_when_version_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            support = self._cursor_support(home)
            support.mkdir(parents=True)
            (support / "product.json").write_text(
                json.dumps({"version": "2.0.0"}),
                encoding="utf-8",
            )
            status = {
                "Cursor": {
                    "enabled": False,
                    "reason": "Consent/source setting disabled",
                    "events": 0,
                }
            }
            enrich_ide_collector_versions(status, home)
            self.assertEqual(status["Cursor"]["version"], "2.0.0")

    def test_windsurf_uses_first_base_dir_with_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            support = home / "Library" / "Application Support"
            next_dir = support / "Windsurf - Next"
            next_dir.mkdir(parents=True)
            (next_dir / "product.json").write_text(
                json.dumps({"version": "1.94.0-next"}),
                encoding="utf-8",
            )
            status = {"Windsurf": {"enabled": True, "reason": "", "events": 1}}
            enrich_ide_collector_versions(status, home)
            self.assertEqual(status["Windsurf"]["version"], "1.94.0-next")


if __name__ == "__main__":
    unittest.main()
