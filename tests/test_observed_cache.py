"""Tests for the observed-hours cache (Part A of the statusline)."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from core.observed_cache import observed_hours_by_project_day, write_observed_summary


def _report(day: str, sessions):
    """A minimal report whose overall_days drive build_reported_proposals."""
    return SimpleNamespace(
        overall_days={day: {"sessions": sessions}},
        args=Namespace(min_session=15, min_session_passive=5),
    )


def _session(day, project, start_h=10, end_h=11):
    start = datetime.fromisoformat(f"{day}T{start_h:02d}:00:00")
    end = datetime.fromisoformat(f"{day}T{end_h:02d}:00:00")
    return (start, end, [{"project": project, "source": "TIMELOG.md"}])


class ObservedCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_then_read_round_trip(self):
        report = _report("2026-06-20", [_session("2026-06-20", "Alpha")])
        written = write_observed_summary(report, home=self.home)
        self.assertEqual(written, 1)
        hours = observed_hours_by_project_day(self.home)
        self.assertIn(("Alpha", "2026-06-20"), hours)
        self.assertGreater(hours[("Alpha", "2026-06-20")], 0)

    def test_latest_write_wins(self):
        # First run sees one session; a later run sees two -> reader returns latest.
        write_observed_summary(_report("2026-06-20", [_session("2026-06-20", "Alpha")]), home=self.home)
        first = observed_hours_by_project_day(self.home)[("Alpha", "2026-06-20")]
        write_observed_summary(
            _report("2026-06-20", [_session("2026-06-20", "Alpha", 10, 11), _session("2026-06-20", "Alpha", 13, 15)]),
            home=self.home,
        )
        latest = observed_hours_by_project_day(self.home)[("Alpha", "2026-06-20")]
        self.assertGreater(latest, first)

    def test_removed_keys_cleared_on_rerun(self):
        # Month replacement: a later snapshot for the same month drops keys it no longer covers.
        write_observed_summary(_report("2026-06-20", [_session("2026-06-20", "Alpha")]), home=self.home)
        self.assertIn(("Alpha", "2026-06-20"), observed_hours_by_project_day(self.home))
        write_observed_summary(_report("2026-06-21", [_session("2026-06-21", "Beta")]), home=self.home)
        hours = observed_hours_by_project_day(self.home)
        self.assertNotIn(("Alpha", "2026-06-20"), hours)
        self.assertIn(("Beta", "2026-06-21"), hours)

    def test_empty_report_writes_nothing(self):
        report = SimpleNamespace(overall_days={}, args=Namespace(min_session=15, min_session_passive=5))
        self.assertEqual(write_observed_summary(report, home=self.home), 0)

    def test_empty_store_reads_empty(self):
        self.assertEqual(observed_hours_by_project_day(self.home), {})


if __name__ == "__main__":
    unittest.main()
