"""Capture runs on a timer without ever writing evidence nobody asked for.

Two halves of "keep it running": the `--if-enabled` gate that lets automation
call capture unconditionally, and the doctor row that makes a device which
stopped reporting visible instead of silently absent.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from rich.table import Table

from core.doctor_device_row import (
    STALE_AFTER_DAYS,
    add_device_coverage_row,
    describe_devices,
)
from core.session_capture import capture_device_evidence

PROFILES = [
    {
        "name": "gittan",
        "project_id": "gittan",
        "match_terms": ["gittan"],
        "tracked_urls": [],
        "aliases": [],
        "canonical_project": "gittan",
        "customer": "internal",
        "email": "",
        "tags": [],
    }
]
DT_FROM = datetime(2026, 7, 25, tzinfo=timezone.utc)
DT_TO = datetime(2026, 7, 26, tzinfo=timezone.utc)


def write_transcript(home: Path) -> None:
    proj = home / ".claude" / "projects" / "-work-gittan"
    proj.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"timestamp": "2026-07-25T09:00:00Z", "type": "user", "message": {"content": "gittan"}}
    )
    (proj / "session.jsonl").write_text(line + "\n", encoding="utf-8")


def write_config(path: Path, shadow_log: str | None) -> Path:
    payload: dict = {"projects": [{"name": "gittan", "match_terms": ["gittan"]}]}
    if shadow_log is not None:
        payload["shadow_log"] = shadow_log
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class IfEnabledGateTests(unittest.TestCase):
    """A timer calls capture every tick; the config decides whether it writes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.store = self.tmp / "store"
        write_transcript(self.home)

    def tearDown(self):
        self._tmp.cleanup()

    def _capture(self, shadow_log, **kwargs):
        cfg = write_config(self.tmp / "projects.json", shadow_log)
        return capture_device_evidence(
            PROFILES,
            DT_FROM,
            DT_TO,
            home=self.home,
            base_dir=self.store,
            device="laptop",
            config_path=str(cfg),
            **kwargs,
        )

    def test_gate_off_writes_nothing_and_says_why(self):
        summary = self._capture("off", if_enabled=True)
        self.assertEqual(summary["skipped_reason"], "shadow_log is not on")
        self.assertEqual(summary["collected"], 0)
        self.assertFalse(self.store.exists())

    def test_missing_setting_is_treated_as_off(self):
        summary = self._capture(None, if_enabled=True)
        self.assertEqual(summary["skipped_reason"], "shadow_log is not on")
        self.assertFalse(self.store.exists())

    def test_gate_on_captures(self):
        summary = self._capture("on", if_enabled=True)
        self.assertIsNone(summary.get("skipped_reason"))
        self.assertGreater(summary["appended"], 0)

    def test_explicit_run_ignores_the_gate(self):
        """Typing `gittan capture` is the consent; a silent no-op would baffle."""
        summary = self._capture("off", if_enabled=False)
        self.assertIsNone(summary.get("skipped_reason"))
        self.assertGreater(summary["appended"], 0)


class DescribeDevicesTests(unittest.TestCase):
    TODAY = date(2026, 7, 25)

    def test_recent_devices_read_naturally_and_sort_first(self):
        rows, stale = describe_devices(
            {
                "phone": {"last_observed_at": "2026-07-24T10:00:00+00:00"},
                "laptop": {"last_observed_at": "2026-07-25T09:00:00+00:00"},
            },
            self.TODAY,
        )
        self.assertEqual(rows, ["laptop: today", "phone: yesterday"])
        self.assertEqual(stale, [])

    def test_device_past_the_threshold_is_flagged(self):
        rows, stale = describe_devices(
            {"phone": {"last_observed_at": "2026-06-25T09:00:00+00:00"}}, self.TODAY
        )
        self.assertEqual(rows, ["phone: 30d ago"])
        self.assertEqual(stale, ["phone"])

    def test_boundary_day_is_not_yet_stale(self):
        edge = f"2026-07-{25 - STALE_AFTER_DAYS:02d}T09:00:00+00:00"
        _rows, stale = describe_devices({"phone": {"last_observed_at": edge}}, self.TODAY)
        self.assertEqual(stale, [])

    def test_unparseable_timestamp_is_flagged_not_hidden(self):
        rows, stale = describe_devices({"phone": {"last_observed_at": "nonsense"}}, self.TODAY)
        self.assertEqual(rows, ["phone: unknown"])
        self.assertEqual(stale, ["phone"])


class DeviceCoverageRowTests(unittest.TestCase):
    def _row(self, per_device, shadow_log="on"):
        table = Table()
        table.add_column("a")
        table.add_column("b")
        table.add_column("c")
        with patch("core.evidence_store.shadow_log_config_setting", return_value=shadow_log), \
             patch("core.evidence_store.store_health", return_value={"per_device": per_device}):
            add_device_coverage_row(
                table,
                Path("cfg.json"),
                ok_icon="OK",
                warn_icon="WARN",
                style_muted="dim",
                today=date(2026, 7, 25),
            )
        return table

    def test_no_row_when_shadow_log_is_off(self):
        """The shadow-log row already explains that state — don't say it twice."""
        self.assertEqual(self._row({}, shadow_log="off").row_count, 0)

    def test_prompts_for_capture_when_no_device_tagged_evidence_exists(self):
        table = self._row({})
        self.assertEqual(table.row_count, 1)
        self.assertEqual(table.columns[1]._cells[0], "WARN")

    def test_healthy_devices_render_ok(self):
        table = self._row({"laptop": {"last_observed_at": "2026-07-25T09:00:00+00:00"}})
        self.assertEqual(table.columns[1]._cells[0], "OK")
        self.assertIn("laptop: today", table.columns[2]._cells[0])

    def test_quiet_device_warns_and_names_itself(self):
        table = self._row(
            {
                "laptop": {"last_observed_at": "2026-07-25T09:00:00+00:00"},
                "phone": {"last_observed_at": "2026-06-01T09:00:00+00:00"},
            }
        )
        self.assertEqual(table.columns[1]._cells[0], "WARN")
        detail = table.columns[2]._cells[0]
        self.assertIn("phone", detail)
        self.assertIn("quiet for over", detail)


if __name__ == "__main__":
    unittest.main()
