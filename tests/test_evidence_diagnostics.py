from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.evidence_diagnostics import build_evidence_snapshot, build_evidence_warnings


class EvidenceDiagnosticsTests(unittest.TestCase):
    def test_snapshot_computes_hours_delta_and_sources(self):
        report = SimpleNamespace(
            included_events=[
                {"source": "Cursor"},
                {"source": "Chrome"},
                {"source": "Cursor"},
            ],
            overall_days={"2026-05-04": {"hours": 1.9}},
            screen_time_days={"2026-05-04": 7.6},
        )
        snap = build_evidence_snapshot(report)
        self.assertAlmostEqual(snap["observed_hours"], 1.9, places=3)
        self.assertAlmostEqual(snap["screen_time_hours"], 7.6, places=3)
        self.assertAlmostEqual(snap["delta_hours"], 5.7, places=3)
        self.assertEqual(snap["source_counts"]["Cursor"], 2)
        self.assertEqual(snap["source_counts"]["Chrome"], 1)

    def test_snapshot_normalizes_screen_time_seconds_to_hours(self):
        report = SimpleNamespace(
            included_events=[],
            overall_days={"2026-05-04": {"hours": 1.0}},
            screen_time_days={"2026-05-04": 7200.0},
        )
        snap = build_evidence_snapshot(report)
        self.assertAlmostEqual(snap["screen_time_hours"], 2.0, places=3)
        self.assertAlmostEqual(snap["delta_hours"], 1.0, places=3)

    def test_snapshot_sums_hours_when_daily_peaks_stay_below_seconds_heuristic(self):
        report = SimpleNamespace(
            included_events=[],
            overall_days={"2026-05-04": {"hours": 1.0}},
            screen_time_days={"2026-05-04": 7.6, "2026-05-05": 8.0},
        )
        snap = build_evidence_snapshot(report)
        self.assertAlmostEqual(snap["screen_time_hours"], 15.6, places=3)


    def test_snapshot_mixed_units_normalizes_each_day_independently(self):
        report = SimpleNamespace(
            included_events=[],
            overall_days={"2026-05-04": {"hours": 1.0}},
            screen_time_days={"2026-05-04": 7.0, "2026-05-05": 7200.0},
        )
        snap = build_evidence_snapshot(report)
        self.assertAlmostEqual(snap["screen_time_hours"], 9.0, places=3)

    def test_warnings_trigger_on_gap_low_diversity_and_low_chrome(self):
        snapshot = {
            "delta_hours": 5.0,
            "source_counts": {"Cursor": 100, "Worklog": 2, "Chrome": 5},
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertTrue(any("Large Screen Time gap" in msg for msg in warnings))
        self.assertTrue(any("Low source diversity" in msg for msg in warnings))
        self.assertTrue(any("Chrome evidence volume is low" in msg for msg in warnings))

    def test_warnings_clear_for_healthy_snapshot(self):
        snapshot = {
            "delta_hours": 0.5,
            "source_counts": {"Cursor": 120, "Chrome": 35, "Worklog": 10, "Claude.ai (web)": 8},
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()

