from __future__ import annotations

import unittest

from scripts.calibration.run_month_end_invoice_check import _top_deltas

CURRENT_HOURS = {"A": 10.0, "B": 5.0, "C": 3.0}
PREVIOUS_HOURS = {"A": 8.0, "B": 9.0, "D": 1.0}


class MonthEndInvoiceCheckTests(unittest.TestCase):
    def test_top_deltas_returns_non_zero_sorted_by_magnitude(self):
        rows = _top_deltas(CURRENT_HOURS, PREVIOUS_HOURS)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["project"], "B")
        self.assertAlmostEqual(float(rows[0]["delta_hours"]), -4.0, places=6)
        projects = [str(r["project"]) for r in rows]
        self.assertIn("A", projects)
        self.assertIn("C", projects)
        self.assertIn("D", projects)


if __name__ == "__main__":
    unittest.main()

