from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.calibration.screen_time_gap import analyze_screen_time_gaps


class ScreenTimeGapAnalysisTests(unittest.TestCase):
    def test_analyze_screen_time_gaps_computes_totals_and_project_alloc(self):
        report = SimpleNamespace(
            overall_days={
                "2026-03-01": {"hours": 5.0},
                "2026-03-02": {"hours": 2.0},
            },
            screen_time_days={
                "2026-03-01": 4.0 * 3600.0,
                "2026-03-02": 3.0 * 3600.0,
            },
            project_reports={
                "A": {
                    "2026-03-01": {"hours": 3.0},
                    "2026-03-02": {"hours": 2.0},
                },
                "B": {
                    "2026-03-01": {"hours": 2.0},
                },
            },
        )
        payload = analyze_screen_time_gaps(report)
        self.assertEqual(len(payload["days"]), 2)
        self.assertAlmostEqual(payload["totals"]["estimated_hours"], 7.0, places=4)
        self.assertAlmostEqual(payload["totals"]["screen_time_hours"], 7.0, places=4)
        self.assertIn("A", payload["project_allocated_gap_hours"])
        self.assertIn("B", payload["project_allocated_gap_hours"])


    def test_coverage_is_inf_when_screen_time_zero_but_estimated_nonzero(self):
        """New in PR: when screen_hours=0 and estimated_hours>0, coverage_ratio must be math.inf."""
        import math
        report = SimpleNamespace(
            overall_days={
                "2026-03-10": {"hours": 3.0},
            },
            screen_time_days={
                "2026-03-10": 0.0,  # zero seconds of screen time
            },
            project_reports={},
        )
        payload = analyze_screen_time_gaps(report)
        day = payload["days"][0]
        self.assertAlmostEqual(day["estimated_hours"], 3.0, places=4)
        self.assertAlmostEqual(day["screen_time_hours"], 0.0, places=4)
        # coverage_ratio stored via as_dict() rounds the value; math.inf rounds to inf
        self.assertTrue(math.isinf(day["coverage_ratio"]))

    def test_coverage_is_one_when_both_zero(self):
        """When both screen_hours=0 and estimated_hours=0, coverage is 1.0 (no gap)."""
        report = SimpleNamespace(
            overall_days={
                "2026-03-15": {"hours": 0.0},
            },
            screen_time_days={
                "2026-03-15": 0.0,
            },
            project_reports={},
        )
        payload = analyze_screen_time_gaps(report)
        day = payload["days"][0]
        self.assertAlmostEqual(day["coverage_ratio"], 1.0, places=4)

    def test_over_attributed_hours_computed_correctly(self):
        """When estimated > screen, over_attributed_hours should be the excess."""
        report = SimpleNamespace(
            overall_days={
                "2026-03-20": {"hours": 8.0},
            },
            screen_time_days={
                "2026-03-20": 5.0 * 3600.0,
            },
            project_reports={},
        )
        payload = analyze_screen_time_gaps(report)
        day = payload["days"][0]
        self.assertAlmostEqual(day["over_attributed_hours"], 3.0, places=4)
        self.assertAlmostEqual(day["unexplained_screen_time_hours"], 0.0, places=4)

    def test_unexplained_screen_time_computed_correctly(self):
        """When screen > estimated, unexplained_screen_time_hours should be the deficit."""
        report = SimpleNamespace(
            overall_days={
                "2026-03-21": {"hours": 2.0},
            },
            screen_time_days={
                "2026-03-21": 6.0 * 3600.0,
            },
            project_reports={},
        )
        payload = analyze_screen_time_gaps(report)
        day = payload["days"][0]
        self.assertAlmostEqual(day["unexplained_screen_time_hours"], 4.0, places=4)
        self.assertAlmostEqual(day["over_attributed_hours"], 0.0, places=4)

    def test_day_with_no_screen_time_entry_uses_zero(self):
        """Days with estimated hours but missing from screen_time_days get zero screen time."""
        import math
        report = SimpleNamespace(
            overall_days={
                "2026-03-22": {"hours": 1.5},
            },
            screen_time_days={},  # no screen time data at all
            project_reports={},
        )
        payload = analyze_screen_time_gaps(report)
        day = payload["days"][0]
        self.assertAlmostEqual(day["screen_time_hours"], 0.0, places=4)
        self.assertTrue(math.isinf(day["coverage_ratio"]))


if __name__ == "__main__":
    unittest.main()
