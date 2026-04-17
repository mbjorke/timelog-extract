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


if __name__ == "__main__":
    unittest.main()

