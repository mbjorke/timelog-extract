from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.calibration.compare_screen_time_gap import (
    compare_totals,
    load_payload,
    render_report,
)


class CompareScreenTimeGapTests(unittest.TestCase):
    def test_compare_totals_returns_expected_delta_rows(self):
        old_payload = {
            "totals": {
                "estimated_hours": 10.0,
                "screen_time_hours": 8.0,
                "coverage_ratio": 0.8,
                "unexplained_screen_time_hours": 1.5,
                "over_attributed_hours": 3.0,
            },
            "days": [],
        }
        new_payload = {
            "totals": {
                "estimated_hours": 12.5,
                "screen_time_hours": 10.0,
                "coverage_ratio": 0.9,
                "unexplained_screen_time_hours": 1.0,
                "over_attributed_hours": 2.0,
            },
            "days": [],
        }
        rows = compare_totals(old_payload, new_payload)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][0], "estimated_hours")
        self.assertAlmostEqual(rows[0][3], 2.5, places=4)

    def test_load_payload_rejects_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"totals": {}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_payload(path)

    def test_render_report_includes_paths_and_day_delta(self):
        old_path = Path("old.json")
        new_path = Path("new.json")
        old_payload = {"totals": {}, "days": [1, 2]}
        new_payload = {"totals": {}, "days": [1, 2, 3]}
        report = render_report(old_path, new_path, old_payload, new_payload)
        self.assertIn("Screen Time Gap Comparison", report)
        self.assertIn("old.json", report)
        self.assertIn("new.json", report)
        self.assertIn("Day rows: 2 -> 3", report)


if __name__ == "__main__":
    unittest.main()
