"""Tests for the persistent shadow-log config default (GH-274).

Precedence: explicit CLI flag > config setting > default off. The store sat
empty for months because capture was flag-only — these tests pin the config
seam so a durability feature never again depends on human flag memory.
"""

import json
import tempfile
import unittest
from pathlib import Path

from rich.table import Table

from core.doctor_shadow_log_row import add_shadow_log_row
from core.evidence_store import (
    capture_if_enabled,
    events_dir,
    evidence_base_dir,
    resolve_shadow_log,
    shadow_log_config_setting,
)


def _ev(source, ts, detail, project="Alpha"):
    return {"source": source, "timestamp": ts, "detail": detail, "project": project}


class ShadowLogConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.cfg = self.home / "timelog_projects.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_cfg(self, payload):
        self.cfg.write_text(json.dumps(payload), encoding="utf-8")

    # --- config reading -------------------------------------------------
    def test_config_setting_reads_top_level_key(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        self.assertEqual(shadow_log_config_setting(self.cfg), "on")

    def test_config_setting_defaults_off(self):
        self._write_cfg({"projects": []})
        self.assertEqual(shadow_log_config_setting(self.cfg), "off")

    def test_config_setting_fails_closed(self):
        # missing file, malformed JSON, and junk values all read as off
        self.assertEqual(shadow_log_config_setting(self.home / "missing.json"), "off")
        self.assertEqual(shadow_log_config_setting(None), "off")
        self.cfg.write_text("{not json", encoding="utf-8")
        self.assertEqual(shadow_log_config_setting(self.cfg), "off")
        self._write_cfg({"projects": [], "shadow_log": "yes please"})
        self.assertEqual(shadow_log_config_setting(self.cfg), "off")

    # --- precedence: flag > config > default off -------------------------
    def test_explicit_flag_wins_over_config(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        self.assertEqual(resolve_shadow_log("off", self.cfg), "off")
        self._write_cfg({"projects": [], "shadow_log": "off"})
        self.assertEqual(resolve_shadow_log("on", self.cfg), "on")

    def test_auto_defers_to_config(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        self.assertEqual(resolve_shadow_log("auto", self.cfg), "on")
        self._write_cfg({"projects": []})
        self.assertEqual(resolve_shadow_log("auto", self.cfg), "off")

    def test_auto_without_config_is_off(self):
        self.assertEqual(resolve_shadow_log("auto", None), "off")
        self.assertEqual(resolve_shadow_log(None, None), "off")

    # --- capture honors the resolved state --------------------------------
    def test_capture_runs_when_config_enables(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        result = capture_if_enabled(
            "auto",
            [_ev("Cursor", "2026-07-02T09:00:00+00:00", "work")],
            home=self.home,
            config_path=self.cfg,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["appended"], 1)
        self.assertTrue(events_dir(evidence_base_dir(self.home)).is_dir())

    def test_capture_skipped_when_flag_off_despite_config_on(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        result = capture_if_enabled(
            "off",
            [_ev("Cursor", "2026-07-02T09:00:00+00:00", "work")],
            home=self.home,
            config_path=self.cfg,
        )
        self.assertIsNone(result)
        self.assertFalse(events_dir(evidence_base_dir(self.home)).is_dir())

    def test_capture_skipped_on_auto_without_config(self):
        result = capture_if_enabled(
            "auto",
            [_ev("Cursor", "2026-07-02T09:00:00+00:00", "work")],
            home=self.home,
            config_path=None,
        )
        self.assertIsNone(result)

    # --- doctor row --------------------------------------------------------
    def _row_texts(self, table):
        return [str(cell) for column in table.columns for cell in column._cells]

    def test_doctor_row_warns_when_off(self):
        self._write_cfg({"projects": []})
        table = Table()
        for _ in range(3):
            table.add_column()
        add_shadow_log_row(
            table, self.cfg, ok_icon="OK", warn_icon="WARN", style_muted="dim", home=self.home
        )
        text = " ".join(self._row_texts(table))
        self.assertIn("WARN", text)
        self.assertIn("Shadow log: off", text)
        self.assertIn('"shadow_log": "on"', text)

    def test_doctor_row_confirms_when_on(self):
        self._write_cfg({"projects": [], "shadow_log": "on"})
        capture_if_enabled(
            "auto",
            [_ev("Cursor", "2026-07-02T09:00:00+00:00", "work")],
            home=self.home,
            config_path=self.cfg,
        )
        table = Table()
        for _ in range(3):
            table.add_column()
        add_shadow_log_row(
            table, self.cfg, ok_icon="OK", warn_icon="WARN", style_muted="dim", home=self.home
        )
        text = " ".join(self._row_texts(table))
        self.assertIn("OK", text)
        self.assertIn("Shadow log: on (config)", text)
        self.assertIn("1 records", text)


if __name__ == "__main__":
    unittest.main()
