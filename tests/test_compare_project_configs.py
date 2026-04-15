"""Tests for truth-payload comparison helpers (config A vs B)."""

import unittest

from core.compare_project_configs import format_comparison_text, project_hours_table


class CompareProjectConfigsTests(unittest.TestCase):
    def test_project_hours_table_merges_keys(self):
        a = {"projects": {"P1": 1.0, "Uncategorized": 0.5}}
        b = {"projects": {"P1": 1.5, "P2": 2.0}}
        rows = project_hours_table(a, b)
        by_name = {r[0]: r for r in rows}
        self.assertEqual(by_name["P1"], ("P1", 1.0, 1.5, 0.5))
        self.assertEqual(by_name["P2"], ("P2", 0.0, 2.0, 2.0))
        self.assertEqual(by_name["Uncategorized"], ("Uncategorized", 0.5, 0.0, -0.5))

    def test_project_hours_table_bad_projects(self):
        with self.assertRaises(TypeError):
            project_hours_table({"projects": "not-a-dict"}, {"projects": {}})

    def test_format_comparison_text_includes_totals(self):
        a = {
            "projects": {"A": 1.0},
            "totals": {"hours_estimated": 3.0, "event_count": 10},
        }
        b = {
            "projects": {"A": 2.0},
            "totals": {"hours_estimated": 4.0, "event_count": 12},
        }
        text = format_comparison_text(a, b)
        self.assertIn("A", text)
        self.assertIn("totals.hours_estimated", text)
        self.assertIn("totals.event_count", text)
        self.assertIn("+1.0000", text)
        self.assertIn("+2", text)


if __name__ == "__main__":
    unittest.main()
