"""Fixture tests for the Timely Memory presence collector (GH-285).

All tests build a synthetic SQLite buffer — never a real capture. They cover
the four Behavior Contract scenarios in
docs/task-prompts/timely-memory-collector-spike-task.md: opt-in only,
read-only access, presence role (comparator, no classified time), and
graceful disappearance.
"""

import argparse
import sqlite3
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from core.presence_sources import collect_timely_memory_status
from core.sources import COVERAGE_COMPARATOR, get_source_role
from core.timely_memory import (
    TIMELY_MEMORY_SOURCE,
    collect_timely_memory,
    detect_timely_memory_db,
    timely_memory_db_candidates,
    timely_memory_source_enabled,
)

TZ = ZoneInfo("Europe/Mariehamn")


def _make_buffer(path: Path, timestamps_utc: list[str]) -> None:
    """Create a synthetic buffer with 1 Hz-style sample rows."""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE captured_entries("
            "id TEXT NOT NULL PRIMARY KEY,"
            "captured_at_utc DATETIME NOT NULL,"
            "window_title TEXT NOT NULL,"
            "app_name TEXT NOT NULL,"
            "uploaded BOOLEAN NOT NULL DEFAULT 0,"
            "captured_at_with_tz TEXT NOT NULL,"
            "details TEXT,"
            "rewritten BOOLEAN NOT NULL DEFAULT FALSE)"
        )
        conn.executemany(
            "INSERT INTO captured_entries"
            "(id, captured_at_utc, window_title, app_name, uploaded, captured_at_with_tz)"
            " VALUES (?, ?, 'synthetic title', 'SyntheticApp', 1, ?)",
            [(f"row-{i}", ts, ts) for i, ts in enumerate(timestamps_utc)],
        )


def _second_series(base: str, start: int, count: int) -> list[str]:
    return [f"{base} 10:{(start + i) // 60:02d}:{(start + i) % 60:02d}" for i in range(count)]


class TestTimelyMemoryCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.db = Path(self.tmp.name) / "db.sqlite"
        self.window = (
            datetime(2026, 7, 2, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 2, 23, 59, 59, tzinfo=timezone.utc),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_opt_in_only_off_by_default(self):
        """Scenario: Opt-in only — off mode never invokes the read path."""
        enabled, reason = timely_memory_source_enabled(argparse.Namespace())
        self.assertFalse(enabled)
        self.assertIn("opt-in", reason)

        status: dict = {}

        def _must_not_run(dt_from, dt_to):
            raise AssertionError("collector ran while disabled")

        result, spans = collect_timely_memory_status(
            args=argparse.Namespace(timely_memory_source="off"),
            dt_from=self.window[0],
            dt_to=self.window[1],
            collector_status=status,
            collect_timely_memory_fn=_must_not_run,
        )
        self.assertIsNone(result)
        self.assertIsNone(spans)
        self.assertFalse(status[TIMELY_MEMORY_SOURCE]["enabled"])
        self.assertIn("opt-in", status[TIMELY_MEMORY_SOURCE]["reason"])

    def test_read_only_source_file_untouched(self):
        """Scenario: Read-only access — bytes and mtime unchanged."""
        _make_buffer(self.db, _second_series("2026-07-02", 0, 120))
        before_bytes = self.db.read_bytes()
        before_mtime = self.db.stat().st_mtime_ns

        days, detail, spans = collect_timely_memory(
            *self.window, candidates=[self.db], local_tz=TZ
        )
        self.assertEqual(detail, str(self.db))
        self.assertEqual(self.db.read_bytes(), before_bytes)
        self.assertEqual(self.db.stat().st_mtime_ns, before_mtime)
        self.assertAlmostEqual(days["2026-07-02"], 120.0)
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(
            (spans[0][1] - spans[0][0]).total_seconds(), 120.0
        )

    def test_span_folding_and_gap_split(self):
        """1 Hz samples fold into spans; gaps > threshold split them."""
        samples = _second_series("2026-07-02", 0, 60) + _second_series(
            "2026-07-02", 300, 30
        )
        _make_buffer(self.db, samples)
        days, _, spans = collect_timely_memory(*self.window, candidates=[self.db], local_tz=TZ)
        self.assertAlmostEqual(days["2026-07-02"], 90.0)
        self.assertEqual(len(spans), 2)

    def test_date_window_filtering(self):
        """Rows outside the requested window are never counted."""
        samples = (
            _second_series("2026-07-01", 0, 60)
            + _second_series("2026-07-02", 0, 60)
            + _second_series("2026-07-03", 0, 60)
        )
        _make_buffer(self.db, samples)
        days, _, spans = collect_timely_memory(*self.window, candidates=[self.db], local_tz=TZ)
        self.assertEqual(set(days), {"2026-07-02"})
        self.assertAlmostEqual(days["2026-07-02"], 60.0)
        self.assertEqual(len(spans), 1)

    def test_presence_role_is_comparator_never_events(self):
        """Scenario: Presence role — comparator context, no classified time."""
        self.assertEqual(get_source_role(TIMELY_MEMORY_SOURCE), COVERAGE_COMPARATOR)

        _make_buffer(self.db, _second_series("2026-07-02", 0, 3600))
        status: dict = {}
        days, spans = collect_timely_memory_status(
            args=argparse.Namespace(timely_memory_source="on"),
            dt_from=self.window[0],
            dt_to=self.window[1],
            collector_status=status,
            collect_timely_memory_fn=lambda a, b: collect_timely_memory(
                a, b, candidates=[self.db], local_tz=TZ
            ),
        )
        # Presence context only: per-day seconds plus a status row — the
        # status path returns no event dicts, so nothing can be classified
        # into project time or billable totals.
        self.assertAlmostEqual(days["2026-07-02"], 3600.0)
        self.assertEqual(len(spans), 1)
        row = status[TIMELY_MEMORY_SOURCE]
        self.assertTrue(row["enabled"])
        self.assertEqual(row["days"], 1)
        self.assertAlmostEqual(row["presence_hours"], 1.0)
        self.assertEqual(row["span_count"], 1)

    def test_source_disappears_gracefully(self):
        """Scenario: Source disappears — unavailable status, run completes."""
        missing = Path(self.tmp.name) / "gone.sqlite"
        self.assertIsNone(detect_timely_memory_db([missing]))

        status: dict = {}
        result, spans = collect_timely_memory_status(
            args=argparse.Namespace(timely_memory_source="on"),
            dt_from=self.window[0],
            dt_to=self.window[1],
            collector_status=status,
            collect_timely_memory_fn=lambda a, b: collect_timely_memory(
                a, b, candidates=[missing], local_tz=TZ
            ),
        )
        self.assertIsNone(result)
        self.assertIsNone(spans)
        row = status[TIMELY_MEMORY_SOURCE]
        self.assertTrue(row["enabled"])
        self.assertIn("not found", row["reason"])
        self.assertEqual(row["days"], 0)

    def test_db_candidates_point_into_home(self):
        home = Path(self.tmp.name)
        candidates = timely_memory_db_candidates(home)
        self.assertTrue(all(str(p).startswith(str(home)) for p in candidates))


if __name__ == "__main__":
    unittest.main()
