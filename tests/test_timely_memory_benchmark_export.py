"""Tests for the Timely Memory benchmark export script (GH-285 slice 2).

Synthetic buffers only — never a real capture.
"""

import sqlite3
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from scripts.run_timely_memory_benchmark_export import (
    Sample,
    fold_spans,
    main,
    presence_minutes_by_local_hour,
    read_samples,
)

TZ = ZoneInfo("Europe/Mariehamn")
UTC = timezone.utc


def _make_buffer(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
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
            "(id, captured_at_utc, window_title, app_name, uploaded, captured_at_with_tz, details)"
            " VALUES (?, ?, ?, ?, 1, ?, ?)",
            [
                (f"row-{i}", ts, title, app, ts, url)
                for i, (ts, app, title, url) in enumerate(rows)
            ],
        )


def _second_rows(base: datetime, count: int, app: str, title: str, url: str = ""):
    return [
        ((base + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S"), app, title, url)
        for i in range(count)
    ]


class TestFoldSpans(unittest.TestCase):
    def _samples(self, base: datetime, count: int, app="App", title="T", url=""):
        return [
            Sample(ts=base + timedelta(seconds=i), app=app, title=title, url=url)
            for i in range(count)
        ]

    def test_contiguous_same_context_is_one_span(self):
        base = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        spans = fold_spans(self._samples(base, 60))
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].seconds, 60)

    def test_context_change_splits_span(self):
        base = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        samples = self._samples(base, 30, title="A") + self._samples(
            base + timedelta(seconds=30), 30, title="B"
        )
        spans = fold_spans(samples)
        self.assertEqual([s.title for s in spans], ["A", "B"])
        self.assertEqual([s.seconds for s in spans], [30, 30])

    def test_gap_splits_span(self):
        base = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        samples = self._samples(base, 10) + self._samples(base + timedelta(seconds=300), 10)
        spans = fold_spans(samples, gap_seconds=30)
        self.assertEqual(len(spans), 2)

    def test_presence_minutes_by_local_hour(self):
        base = datetime(2026, 7, 3, 10, 59, 30, tzinfo=UTC)  # 13:59:30 local EEST
        minutes = presence_minutes_by_local_hour(self._samples(base, 60), TZ)
        self.assertEqual(minutes, {"13": 0.5, "14": 0.5})


class TestExportEndToEnd(unittest.TestCase):
    def test_export_writes_tsvs_and_filters_window(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.sqlite"
            rows = (
                _second_rows(datetime(2026, 7, 2, 10, 0), 60, "OldApp", "old day")
                + _second_rows(datetime(2026, 7, 3, 10, 0), 120, "Aftershoot", "culling")
                + _second_rows(
                    datetime(2026, 7, 3, 11, 0), 60, "Google Chrome", "Lovable App", "https://x"
                )
            )
            _make_buffer(db, rows)
            out = Path(tmp) / "private" / "benchmarks"

            rc = main(
                [
                    "--day",
                    "2026-07-03",
                    "--tz",
                    "Europe/Mariehamn",
                    "--db",
                    str(db),
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            memories = (out / "timely-2026-07-03-memories.tsv").read_text().splitlines()
            self.assertEqual(len(memories), 3)  # header + 2 spans
            self.assertIn("Aftershoot\tculling", memories[1])
            self.assertIn("https://x", memories[2])
            self.assertNotIn("OldApp", "\n".join(memories))

            presence = (out / "timely-2026-07-03-presence.tsv").read_text().splitlines()
            self.assertEqual(presence[0], "local_hour\tpresence_minutes")
            self.assertIn("13\t2.0", presence[1])  # 10:00 UTC = 13:00 EEST
            self.assertIn("14\t1.0", presence[2])

    def test_refuses_output_outside_private(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.sqlite"
            _make_buffer(db, _second_rows(datetime(2026, 7, 3, 10, 0), 5, "App", "t"))
            with self.assertRaises(SystemExit) as ctx:
                main(
                    [
                        "--day",
                        "2026-07-03",
                        "--db",
                        str(db),
                        "--out",
                        str(Path(tmp) / "not-private"),
                    ]
                )
            self.assertIn("private", str(ctx.exception))

    def test_source_file_untouched(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.sqlite"
            _make_buffer(db, _second_rows(datetime(2026, 7, 3, 10, 0), 30, "App", "t"))
            before = (db.read_bytes(), db.stat().st_mtime_ns)
            read_samples(
                db,
                datetime(2026, 7, 3, 0, 0, tzinfo=TZ),
                datetime(2026, 7, 4, 0, 0, tzinfo=TZ),
            )
            self.assertEqual((db.read_bytes(), db.stat().st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()
