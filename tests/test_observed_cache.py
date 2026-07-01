"""Tests for the observed-hours cache (Part A of the statusline)."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from core.observed_cache import (
    observed_hours_by_project_day,
    observed_last_capture_date,
    write_observed_summary,
)


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

    def test_prior_keys_preserved_on_rerun(self):
        # keep-max never drops a (project, day) a later run no longer covers — evidence
        # for closed days decays, and a rerun must not erase what an earlier run captured.
        write_observed_summary(_report("2026-06-20", [_session("2026-06-20", "Alpha")]), home=self.home)
        write_observed_summary(_report("2026-06-21", [_session("2026-06-21", "Beta")]), home=self.home)
        hours = observed_hours_by_project_day(self.home)
        self.assertIn(("Alpha", "2026-06-20"), hours)
        self.assertIn(("Beta", "2026-06-21"), hours)

    def test_lower_rerun_keeps_max(self):
        # Evidence decay: a later run seeing fewer hours must NOT lower the stored value.
        write_observed_summary(
            _report(
                "2026-03-10",
                [_session("2026-03-10", "Alpha", 10, 11), _session("2026-03-10", "Alpha", 13, 15)],
            ),
            home=self.home,
        )
        peak = observed_hours_by_project_day(self.home)[("Alpha", "2026-03-10")]
        write_observed_summary(
            _report("2026-03-10", [_session("2026-03-10", "Alpha", 10, 11)]), home=self.home
        )
        after = observed_hours_by_project_day(self.home)[("Alpha", "2026-03-10")]
        self.assertEqual(after, peak)  # keep-max: the lower rerun did not degrade it

    def test_malformed_existing_rows_are_skipped(self):
        # Valid-JSON-but-wrong-shape cache lines must be skipped, not crash the merge.
        from core.observed_cache import _month_path, observed_base_dir

        base = observed_base_dir(self.home)
        base.mkdir(parents=True, exist_ok=True)
        _month_path(base, "2026-03").write_text(
            "[1, 2, 3]\n"  # JSON list, not a dict
            '{"project": "", "date": "2026-03-01", "hours": 1}\n'  # empty project
            '{"project": "Beta", "date": "2026-03-02", "hours": "x"}\n'  # non-numeric hours
            '{"project": "Beta", "date": "2026-03-02", "hours": 2.5}\n',  # valid
            encoding="utf-8",
        )
        written = write_observed_summary(
            _report("2026-03-03", [_session("2026-03-03", "Alpha")]), home=self.home
        )
        hours = observed_hours_by_project_day(self.home)
        self.assertGreater(written, 0)
        self.assertIn(("Alpha", "2026-03-03"), hours)  # new row landed
        self.assertEqual(hours[("Beta", "2026-03-02")], 2.5)  # only the valid existing row survived

    def test_empty_report_writes_nothing(self):
        report = SimpleNamespace(overall_days={}, args=Namespace(min_session=15, min_session_passive=5))
        self.assertEqual(write_observed_summary(report, home=self.home), 0)

    def test_empty_store_reads_empty(self):
        self.assertEqual(observed_hours_by_project_day(self.home), {})

    def test_last_capture_date_none_when_empty(self):
        self.assertIsNone(observed_last_capture_date(self.home))

    def test_last_capture_date_is_write_day(self):
        write_observed_summary(_report("2026-06-20", [_session("2026-06-20", "Alpha")]), home=self.home)
        today = datetime.now().date().isoformat()
        self.assertEqual(observed_last_capture_date(self.home), today)


if __name__ == "__main__":
    unittest.main()
