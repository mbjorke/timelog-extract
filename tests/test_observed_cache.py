"""Tests for the observed-hours cache (Part A of the statusline)."""

from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.observed_cache import (
    _month_path,
    detect_reattribution,
    observed_base_dir,
    observed_hours_by_project_day,
    observed_last_capture_date,
    observed_lifetime_hours,
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

    def test_read_failure_does_not_wipe_month(self):
        # Fail closed: if the existing month file can't be read, the write must NOT
        # overwrite it with a partial/empty merge (that would be data loss).
        base = observed_base_dir(self.home)
        base.mkdir(parents=True, exist_ok=True)
        mf = _month_path(base, "2026-03")
        mf.write_text(
            '{"captured_at": "", "date": "2026-03-01", "hours": 3.0, "project": "Alpha"}\n',
            encoding="utf-8",
        )
        original = mf.read_text(encoding="utf-8")
        real_open = Path.open

        def boom_on_read(self, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if self == mf and "r" in mode:
                raise OSError("simulated read failure")
            return real_open(self, *args, **kwargs)

        with mock.patch.object(Path, "open", boom_on_read):
            write_observed_summary(
                _report("2026-03-05", [_session("2026-03-05", "Beta")]), home=self.home
            )
        self.assertEqual(mf.read_text(encoding="utf-8"), original)  # untouched

    def test_malformed_existing_rows_are_skipped(self):
        # Valid-JSON-but-wrong-shape cache lines must be skipped, not crash the merge.
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


class ReattributionDetectionTests(unittest.TestCase):
    """GH-544 scenario 3: observed→rescan split shuffle is detectable before keep-max."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.day = "2026-08-07"

    def tearDown(self):
        self._tmp.cleanup()

    def test_detect_reattribution_gh544_shape(self):
        # Same shape as tests/test_reconcile_snapshot.py and the issue instrument:
        # day total roughly holds while hours move Alpha → Beta.
        findings = detect_reattribution(
            {("Alpha", self.day): 0.02, ("Beta", self.day): 5.81},
            {("Alpha", self.day): 1.65, ("Beta", self.day): 4.60},
        )
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["date"], self.day)
        self.assertGreater(finding["shift_share"], 0.75)
        self.assertEqual([row["project"] for row in finding["losers"]], ["Alpha"])
        self.assertEqual([row["project"] for row in finding["gainers"]], ["Beta"])

    def test_detect_skips_uniform_growth(self):
        findings = detect_reattribution(
            {("Alpha", self.day): 2.0, ("Beta", self.day): 5.0},
            {("Alpha", self.day): 1.65, ("Beta", self.day): 4.60},
        )
        self.assertEqual(findings, [])

    def test_detect_skips_days_without_overlap(self):
        findings = detect_reattribution(
            {("Alpha", "2026-08-08"): 1.0},
            {("Alpha", self.day): 1.65, ("Beta", self.day): 4.60},
        )
        self.assertEqual(findings, [])

    def test_detect_skips_coverage_swap_against_keep_max_union(self):
        # Keep-max can retain Alpha from one run and Beta from another; a later
        # report that only covers Gamma must not look like re-attribution.
        findings = detect_reattribution(
            {("Gamma", self.day): 4.0},
            {("Alpha", self.day): 2.0, ("Beta", self.day): 2.0},
        )
        self.assertEqual(findings, [])

    def test_write_attaches_findings_before_keep_max(self):
        base = observed_base_dir(self.home)
        base.mkdir(parents=True, exist_ok=True)
        _month_path(base, "2026-08").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "project": "Alpha",
                            "date": self.day,
                            "hours": 1.65,
                            "captured_at": "",
                        }
                    ),
                    json.dumps(
                        {
                            "project": "Beta",
                            "date": self.day,
                            "hours": 4.60,
                            "captured_at": "",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report = _report(self.day, [_session(self.day, "Alpha")])
        current = {("Alpha", self.day): 0.02, ("Beta", self.day): 5.81}
        with mock.patch(
            "core.observed_cache.report_project_day_hours",
            return_value=current,
        ):
            write_observed_summary(report, home=self.home)
        findings = getattr(report, "reattribution_vs_observed", None)
        self.assertIsNotNone(findings)
        assert findings is not None
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["date"], self.day)
        hours = observed_hours_by_project_day(self.home)
        # keep-max: Alpha's earlier peak stays; Beta rises to the rescan value.
        self.assertEqual(hours[("Alpha", self.day)], 1.65)
        self.assertEqual(hours[("Beta", self.day)], 5.81)


class ObservedLifetimeHoursTests(unittest.TestCase):
    """GH-537: lifetime totals per project, from the cache rather than a re-scan."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, day, project):
        write_observed_summary(_report(day, [_session(day, project)]), home=self.home)

    def test_empty_cache_yields_no_totals_and_no_window(self):
        totals, window = observed_lifetime_hours(self.home)
        self.assertEqual(totals, {})
        self.assertIsNone(window)

    def test_sums_across_days_and_months_per_project(self):
        self._write("2026-05-20", "Alpha")
        self._write("2026-06-20", "Alpha")
        self._write("2026-06-21", "Beta")
        totals, _window = observed_lifetime_hours(self.home)
        per_day = observed_hours_by_project_day(self.home)
        self.assertAlmostEqual(
            totals["Alpha"],
            per_day[("Alpha", "2026-05-20")] + per_day[("Alpha", "2026-06-20")],
        )
        self.assertAlmostEqual(totals["Beta"], per_day[("Beta", "2026-06-21")])

    def test_window_is_the_span_the_cache_actually_covers(self):
        # The figure must never imply coverage the store does not have: the cache
        # is what survived retention, so "all time" would be a false claim.
        self._write("2026-05-20", "Alpha")
        self._write("2026-06-21", "Beta")
        _totals, window = observed_lifetime_hours(self.home)
        self.assertEqual(window, ("2026-05-20", "2026-06-21"))

    def test_no_collector_runs_and_the_cache_is_not_written(self):
        self._write("2026-06-20", "Alpha")
        before = sorted((p.name, p.read_bytes()) for p in observed_base_dir(self.home).glob("*.jsonl"))
        observed_lifetime_hours(self.home)
        after = sorted((p.name, p.read_bytes()) for p in observed_base_dir(self.home).glob("*.jsonl"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
