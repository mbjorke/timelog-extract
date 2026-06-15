from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.evidence_diagnostics import (
    LOW_COVERAGE_RATIO,
    build_evidence_snapshot,
    build_evidence_warnings,
)


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

    def test_snapshot_reports_collected_but_excluded_and_silent_ai_sources(self):
        report = SimpleNamespace(
            included_events=[{"source": "Cursor"}],
            all_events=[
                {"source": "Cursor"},
                {"source": "Claude Desktop"},
                {"source": "Claude Desktop"},
            ],
            overall_days={"2026-06-11": {"hours": 1.0}},
            screen_time_days={},
        )
        snap = build_evidence_snapshot(report)
        self.assertEqual(snap["collected_but_excluded"], {"Claude Desktop": 2})
        self.assertIn("Claude Code CLI", snap["silent_ai_sources"])
        self.assertIn("Gemini CLI", snap["silent_ai_sources"])
        self.assertNotIn("Claude Desktop", snap["silent_ai_sources"])

    def test_healthy_monthly_gap_stays_silent(self):
        snapshot = {
            "observed_hours": 110.0,
            "screen_time_hours": 149.0,
            "delta_hours": 39.0,
            "collected_but_excluded": {},
            "excluded_uncategorized_events": 0,
            "codec_blocked": [],
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertEqual(warnings, [])
        self.assertGreater(snapshot["observed_hours"] / snapshot["screen_time_hours"], LOW_COVERAGE_RATIO)

    def test_low_coverage_warns_when_mappable_signal_exists(self):
        snapshot = {
            "observed_hours": 5.5,
            "screen_time_hours": 15.0,
            "delta_hours": 9.5,
            "collected_but_excluded": {"Claude Desktop": 12},
            "excluded_uncategorized_events": 0,
            "codec_blocked": [],
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertTrue(any("Low project coverage" in msg for msg in warnings))

    def test_low_coverage_silent_without_mappable_signal(self):
        snapshot = {
            "observed_hours": 5.5,
            "screen_time_hours": 15.0,
            "delta_hours": 9.5,
            "collected_but_excluded": {},
            "excluded_uncategorized_events": 0,
            "codec_blocked": [],
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertEqual(warnings, [])

    def test_over_attribution_does_not_trigger_under_coverage_warning(self):
        snapshot = {
            "observed_hours": 16.0,
            "screen_time_hours": 15.0,
            "delta_hours": -1.0,
            "collected_but_excluded": {"Chrome": 5},
            "excluded_uncategorized_events": 10,
            "codec_blocked": [],
        }
        warnings = build_evidence_warnings(snapshot)
        self.assertFalse(any("Low project coverage" in msg for msg in warnings))

    @patch("core.evidence_diagnostics.codec_blocked_sources")
    def test_codec_blocked_surfaces_install_hint(self, mock_blocked):
        mock_blocked.return_value = [
            ("Claude Desktop (Code)", "zstandard codec missing"),
        ]
        snapshot = {
            "observed_hours": 8.0,
            "screen_time_hours": 8.0,
            "codec_blocked": [],
        }
        warnings = build_evidence_warnings(snapshot, home=Path("/tmp"))
        self.assertTrue(any("cache-evidence" in msg for msg in warnings))


if __name__ == "__main__":
    unittest.main()
