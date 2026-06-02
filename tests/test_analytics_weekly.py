from __future__ import annotations

import unittest

from core.analytics_weekly import iso_week_label, pivot_hours_by_week_project


def _reports(mapping):
    """Build a project_reports-shaped dict from {project: {day: hours}}."""
    return {
        project: {day: {"hours": hours} for day, hours in days.items()}
        for project, days in mapping.items()
    }


class IsoWeekLabelTests(unittest.TestCase):
    def test_basic_week(self):
        # 2026-04-01 is a Wednesday in ISO week 14.
        self.assertEqual(iso_week_label("2026-04-01"), "2026-W14")

    def test_zero_padded(self):
        self.assertEqual(iso_week_label("2026-01-05"), "2026-W02")

    def test_year_boundary_belongs_to_prior_iso_year(self):
        # 2022-01-01 is ISO week 52 of 2021.
        self.assertEqual(iso_week_label("2022-01-01"), "2021-W52")


class WeeklyPivotTests(unittest.TestCase):
    def test_empty(self):
        pivot = pivot_hours_by_week_project({})
        self.assertTrue(pivot.is_empty)
        self.assertEqual(pivot.weeks, [])
        self.assertEqual(pivot.grand_total, 0.0)

    def test_single_project_single_day(self):
        pivot = pivot_hours_by_week_project(_reports({"Alpha": {"2026-04-01": 2.0}}))
        self.assertEqual(pivot.weeks, ["2026-W14"])
        self.assertEqual(pivot.projects, ["Alpha"])
        self.assertEqual(pivot.cells["2026-W14"]["Alpha"], 2.0)
        self.assertEqual(pivot.week_totals["2026-W14"], 2.0)
        self.assertEqual(pivot.project_totals["Alpha"], 2.0)
        self.assertEqual(pivot.grand_total, 2.0)

    def test_days_in_same_week_sum(self):
        pivot = pivot_hours_by_week_project(
            _reports({"Alpha": {"2026-03-30": 1.0, "2026-04-01": 1.5}})  # both ISO W14
        )
        self.assertEqual(pivot.weeks, ["2026-W14"])
        self.assertEqual(pivot.cells["2026-W14"]["Alpha"], 2.5)

    def test_multi_project_multi_week_totals(self):
        pivot = pivot_hours_by_week_project(
            _reports({
                "Alpha": {"2026-04-01": 2.0, "2026-04-08": 3.0},  # W14, W15
                "Beta": {"2026-04-01": 1.0},                       # W14
            })
        )
        self.assertEqual(pivot.weeks, ["2026-W14", "2026-W15"])
        self.assertEqual(pivot.projects, ["Alpha", "Beta"])
        self.assertEqual(pivot.cells["2026-W14"]["Alpha"], 2.0)
        self.assertEqual(pivot.cells["2026-W14"]["Beta"], 1.0)
        self.assertEqual(pivot.cells["2026-W15"]["Alpha"], 3.0)
        self.assertNotIn("Beta", pivot.cells["2026-W15"])
        self.assertEqual(pivot.week_totals["2026-W14"], 3.0)
        self.assertEqual(pivot.week_totals["2026-W15"], 3.0)
        self.assertEqual(pivot.project_totals["Alpha"], 5.0)
        self.assertEqual(pivot.project_totals["Beta"], 1.0)
        self.assertEqual(pivot.grand_total, 6.0)

    def test_zero_hour_days_ignored(self):
        pivot = pivot_hours_by_week_project(
            _reports({"Alpha": {"2026-04-01": 0.0, "2026-04-02": 1.0}})
        )
        self.assertEqual(pivot.cells["2026-W14"]["Alpha"], 1.0)

    def test_rounding(self):
        pivot = pivot_hours_by_week_project(
            _reports({"Alpha": {"2026-04-01": 1.111, "2026-04-02": 1.111}})
        )
        self.assertEqual(pivot.cells["2026-W14"]["Alpha"], 2.22)


if __name__ == "__main__":
    unittest.main()
