"""Evidence is filed per device so a shared data repo has nothing to merge.

Two devices committing the same `~/.gittan` repo used to collide on one monthly
file, and git's resolution (keep both sides) silently broke the order-dependent
hash chain. Filing by device removes the collision; repair fixes stores that
already hit it.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.evidence_store import (
    _device_slug,
    _record_file_key,
    capture_events,
    events_dir,
    repair_store,
    store_health,
)


def event(hour: int, detail: str, device: str | None = None) -> dict:
    ev = {
        "source": "Claude Code CLI",
        "timestamp": datetime(2026, 7, 25, hour, 0, tzinfo=timezone.utc),
        "detail": detail,
        "project": "gittan",
    }
    if device is not None:
        ev["source_provenance"] = {"device": device, "captured_via": "claude-code"}
    return ev


class DeviceSlugTests(unittest.TestCase):
    def test_slug_is_filename_safe(self):
        self.assertEqual(_device_slug("Marcus' MacBook Pro"), "marcus-macbook-pro")
        self.assertEqual(_device_slug("claude/web:container"), "claude-web-container")

    def test_missing_device_is_empty(self):
        self.assertEqual(_device_slug(None), "")
        self.assertEqual(_device_slug("   "), "")

    def test_slug_is_bounded(self):
        self.assertLessEqual(len(_device_slug("x" * 200)), 40)

    def test_file_key_falls_back_to_plain_month(self):
        self.assertEqual(_record_file_key({"observed_at": "2026-07-25T09:00:00+00:00"}), "2026-07")

    def test_file_key_includes_the_device(self):
        key = _record_file_key(
            {"observed_at": "2026-07-25T09:00:00+00:00", "source_provenance": {"device": "phone"}}
        )
        self.assertEqual(key, "2026-07.phone")

    def test_malformed_provenance_does_not_crash_filing(self):
        key = _record_file_key(
            {"observed_at": "2026-07-25T09:00:00+00:00", "source_provenance": "not-a-dict"}
        )
        self.assertEqual(key, "2026-07")


class DeviceFilingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "evidence"

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_device_writes_its_own_file(self):
        capture_events([event(9, "laptop A", "laptop")], base_dir=self.base)
        capture_events([event(11, "phone C", "phone")], base_dir=self.base)
        names = sorted(p.name for p in events_dir(self.base).glob("*.jsonl"))
        self.assertEqual(names, ["2026-07.laptop.jsonl", "2026-07.phone.jsonl"])

    def test_two_devices_keep_independent_valid_chains(self):
        capture_events([event(9, "laptop A", "laptop"), event(10, "laptop B", "laptop")], base_dir=self.base)
        capture_events([event(11, "phone C", "phone"), event(12, "phone D", "phone")], base_dir=self.base)
        health = store_health(base_dir=self.base)
        self.assertTrue(health["chain_ok"], health["chain_breaks"])
        self.assertEqual(health["total_records"], 4)

    def test_devices_never_touch_each_others_files(self):
        """The property that makes a shared git repo conflict-free."""
        capture_events([event(9, "laptop A", "laptop")], base_dir=self.base)
        laptop_file = events_dir(self.base) / "2026-07.laptop.jsonl"
        before = laptop_file.read_text(encoding="utf-8")
        capture_events([event(11, "phone C", "phone")], base_dir=self.base)
        self.assertEqual(laptop_file.read_text(encoding="utf-8"), before)

    def test_undeviced_records_keep_the_legacy_filename(self):
        capture_events([event(9, "legacy")], base_dir=self.base)
        self.assertTrue((events_dir(self.base) / "2026-07.jsonl").is_file())

    def test_dedup_still_spans_files(self):
        """The same observation from two devices is one record, not two."""
        capture_events([event(9, "same work", "laptop")], base_dir=self.base)
        result = capture_events([event(9, "same work", "phone")], base_dir=self.base)
        self.assertEqual(result["appended"], 0)
        self.assertEqual(store_health(base_dir=self.base)["total_records"], 1)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "evidence"

    def tearDown(self):
        self._tmp.cleanup()

    def _merged_like_git(self) -> Path:
        """Build the store a git merge produces: two chains concatenated in one file."""
        a = Path(self._tmp.name) / "a"
        b = Path(self._tmp.name) / "b"
        capture_events([event(9, "A1"), event(10, "A2")], base_dir=a)
        capture_events([event(11, "B1"), event(12, "B2")], base_dir=b)
        merged_file = events_dir(self.base) / "2026-07.jsonl"
        merged_file.parent.mkdir(parents=True, exist_ok=True)
        merged_file.write_text(
            (events_dir(a) / "2026-07.jsonl").read_text(encoding="utf-8")
            + (events_dir(b) / "2026-07.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return merged_file

    def test_git_style_merge_breaks_the_chain(self):
        self._merged_like_git()
        self.assertFalse(store_health(base_dir=self.base)["chain_ok"])

    def test_repair_relinks_without_losing_records(self):
        self._merged_like_git()
        result = repair_store(base_dir=self.base)
        self.assertEqual(result["files_repaired"], 1)
        health = store_health(base_dir=self.base)
        self.assertTrue(health["chain_ok"], health["chain_breaks"])
        self.assertEqual(health["total_records"], 4, "repair must not drop real observations")

    def test_repair_drops_duplicates_kept_by_a_merge(self):
        merged_file = self._merged_like_git()
        merged_file.write_text(
            merged_file.read_text(encoding="utf-8") * 2, encoding="utf-8"
        )
        result = repair_store(base_dir=self.base)
        self.assertEqual(result["duplicates_removed"], 4)
        self.assertEqual(store_health(base_dir=self.base)["total_records"], 4)

    def test_repair_is_idempotent(self):
        self._merged_like_git()
        repair_store(base_dir=self.base)
        again = repair_store(base_dir=self.base)
        self.assertEqual(again["files_repaired"], 0)
        self.assertEqual(again["duplicates_removed"], 0)

    def test_repair_on_a_healthy_store_changes_nothing(self):
        capture_events([event(9, "A", "laptop"), event(10, "B", "laptop")], base_dir=self.base)
        result = repair_store(base_dir=self.base)
        self.assertEqual(result["files_repaired"], 0)
        self.assertTrue(store_health(base_dir=self.base)["chain_ok"])

    def test_repair_without_a_store_is_a_no_op(self):
        result = repair_store(base_dir=self.base)
        self.assertFalse(result["enabled"])


if __name__ == "__main__":
    unittest.main()
