"""Tests for the golden-eval HOME materializers (tests/golden_home_fixtures.py)."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from golden_home_fixtures import chrome_synth_visits, materialize_home

from scripts.run_golden_eval import dataset_home

REPO_ROOT = Path(__file__).resolve().parent.parent

CHROME_HISTORY_REL = Path("Library") / "Application Support" / "Google" / "Chrome"


class ChromeSynthVisitsTests(unittest.TestCase):
    def test_series_is_evenly_spaced_and_indexed(self):
        visits = chrome_synth_visits(
            {
                "url_template": "https://dash.example/page?n={i}",
                "title_template": "Dash {i}",
                "count": 4,
                "start": "2026-07-13T09:00:00Z",
                "span_minutes": 60,
            }
        )
        self.assertEqual(len(visits), 4)
        # step = span / count = 15 min, so the last visit sits one step short of the span.
        self.assertEqual(
            [v[0] for v in visits],
            [
                datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 13, 9, 15, tzinfo=timezone.utc),
                datetime(2026, 7, 13, 9, 30, tzinfo=timezone.utc),
                datetime(2026, 7, 13, 9, 45, tzinfo=timezone.utc),
            ],
        )
        self.assertEqual(visits[2][1], "https://dash.example/page?n=2")
        self.assertEqual(visits[2][2], "Dash 2")

    def test_naive_start_is_treated_as_utc(self):
        visits = chrome_synth_visits(
            {"url_template": "https://a.example/", "count": 1, "start": "2026-07-13T09:00:00"}
        )
        self.assertEqual(visits[0][0], datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc))

    def test_zero_count_is_empty(self):
        self.assertEqual(
            chrome_synth_visits({"url_template": "https://a.example/", "count": 0}), []
        )


class MaterializeHomeTests(unittest.TestCase):
    def setUp(self):
        self.homes: list[Path] = []

    def tearDown(self):
        for home in self.homes:
            shutil.rmtree(home, ignore_errors=True)

    def _materialize(self, specs) -> Path:
        home = materialize_home(specs, REPO_ROOT)
        self.homes.append(home)
        return home

    def test_chrome_history_lands_where_the_collector_looks(self):
        home = self._materialize(
            [
                {
                    "kind": "chrome_history",
                    "synth": {
                        "url_template": "https://dash.example/page?n={i}",
                        "count": 5,
                        "start": "2026-07-13T09:00:00Z",
                        "span_minutes": 60,
                    },
                }
            ]
        )
        db_path = home / CHROME_HISTORY_REL / "Default" / "History"
        self.assertTrue(db_path.is_file(), f"no History DB at {db_path}")
        conn = sqlite3.connect(str(db_path))
        try:
            visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
            urls = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(visits, 5)
        self.assertEqual(urls, 5, "each distinct URL should get one urls row")

    def test_repeated_url_reuses_one_urls_row(self):
        home = self._materialize(
            [
                {
                    "kind": "chrome_history",
                    "visits": [
                        {"url": "https://dash.example/", "at": "2026-07-13T09:00:00Z"},
                        {"url": "https://dash.example/", "at": "2026-07-13T10:00:00Z"},
                        {"url": "https://other.example/", "at": "2026-07-13T11:00:00Z"},
                    ],
                }
            ]
        )
        conn = sqlite3.connect(str(home / CHROME_HISTORY_REL / "Default" / "History"))
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0], 2)
        finally:
            conn.close()

    def test_named_profile_is_honored(self):
        home = self._materialize(
            [
                {
                    "kind": "chrome_history",
                    "profile": "Profile 1",
                    "visits": [{"url": "https://a.example/", "at": "2026-07-13T09:00:00Z"}],
                }
            ]
        )
        self.assertTrue((home / CHROME_HISTORY_REL / "Profile 1" / "History").is_file())

    def test_chrome_fixture_without_visits_is_rejected(self):
        with self.assertRaises(ValueError):
            self._materialize([{"kind": "chrome_history"}])

    def test_unknown_kind_names_the_known_kinds(self):
        with self.assertRaises(ValueError) as ctx:
            self._materialize([{"kind": "nope"}])
        self.assertIn("chrome_history", str(ctx.exception))

    def test_cursor_composer_headers_writes_item_table(self):
        home = self._materialize(
            [
                {
                    "kind": "cursor_composer_headers",
                    "path": "tests/fixtures/golden_cursor_composer_headers.json",
                }
            ]
        )
        cursor_dir = home / "Library" / "Application Support" / "Cursor"
        db_path = cursor_dir / "User" / "globalStorage" / "state.vscdb"
        self.assertTrue(db_path.is_file())
        self.assertTrue((cursor_dir / "logs").is_dir(), "collect_cursor needs a logs dir")
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key = ?", ("composer.composerHeaders",)
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)


class MaterializeFailureTests(unittest.TestCase):
    def test_a_failed_spec_leaves_no_home_behind(self):
        """The caller never saw the path, so a half-built home has no owner."""
        created: list[Path] = []
        real_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created.append(Path(path))
            return path

        with patch("golden_home_fixtures.tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            with self.assertRaises(ValueError):
                materialize_home(
                    [
                        {
                            "kind": "chrome_history",
                            "visits": [{"url": "https://a.example/", "at": "2026-07-13T09:00:00Z"}],
                        },
                        {"kind": "nope"},  # fails after the first spec already wrote
                    ],
                    REPO_ROOT,
                )
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0].exists(), f"leaked {created[0]}")


class DatasetHomeTests(unittest.TestCase):
    """HOME is process-global: leaving it pointed at a deleted dir poisons the rest."""

    DATASET = {
        "home_fixtures": [
            {
                "kind": "chrome_history",
                "visits": [{"url": "https://a.example/", "at": "2026-07-13T09:00:00Z"}],
            }
        ]
    }

    def test_home_is_set_inside_and_restored_after(self):
        before = os.environ.get("HOME")
        with dataset_home(REPO_ROOT, self.DATASET) as home:
            self.assertIsNotNone(home)
            self.assertEqual(os.environ["HOME"], str(home))
        self.assertEqual(os.environ.get("HOME"), before)

    def test_temp_home_is_removed_after_the_block(self):
        with dataset_home(REPO_ROOT, self.DATASET) as home:
            captured = home
        self.assertFalse(captured.exists())

    def test_home_is_restored_even_when_the_body_raises(self):
        before = os.environ.get("HOME")
        captured: list[Path] = []
        with self.assertRaises(RuntimeError):
            with dataset_home(REPO_ROOT, self.DATASET) as home:
                captured.append(home)
                raise RuntimeError("report blew up")
        self.assertEqual(os.environ.get("HOME"), before)
        self.assertFalse(captured[0].exists(), "a raising body must not leak the fixture")

    def test_a_dataset_without_fixtures_leaves_home_alone(self):
        before = os.environ.get("HOME")
        with dataset_home(REPO_ROOT, {}) as home:
            self.assertIsNone(home)
            self.assertEqual(os.environ.get("HOME"), before)
        self.assertEqual(os.environ.get("HOME"), before)

    def test_absent_home_is_unset_again_not_set_to_empty(self):
        before = os.environ.pop("HOME", None)
        try:
            with dataset_home(REPO_ROOT, self.DATASET):
                self.assertIn("HOME", os.environ)
            self.assertNotIn("HOME", os.environ)
        finally:
            if before is not None:
                os.environ["HOME"] = before


if __name__ == "__main__":
    unittest.main()
