from __future__ import annotations

import unittest

from core.cli_triage import resolve_target_project_name, select_triage_days


class CliTriageHelpersTests(unittest.TestCase):
    def test_select_triage_days_sorts_by_unexplained_desc(self):
        payload = {
            "days": [
                {"day": "2026-04-01", "unexplained_screen_time_hours": 1.0},
                {"day": "2026-04-02", "unexplained_screen_time_hours": 3.0},
                {"day": "2026-04-03", "unexplained_screen_time_hours": 0.0},
            ]
        }
        rows = select_triage_days(payload, max_days=2)
        self.assertEqual([row["day"] for row in rows], ["2026-04-02", "2026-04-01"])

    def test_resolve_target_project_name_prefers_exact_name(self):
        profiles = [
            {"name": "Project A", "canonical_project": "Suite"},
            {"name": "Project B", "canonical_project": "Suite"},
        ]
        self.assertEqual(resolve_target_project_name(profiles, "Project B"), "Project B")

    def test_resolve_target_project_name_falls_back_to_first_canonical_match(self):
        profiles = [
            {"name": "Project A", "canonical_project": "Suite"},
            {"name": "Project B", "canonical_project": "Suite"},
        ]
        self.assertEqual(resolve_target_project_name(profiles, "Suite"), "Project A")


if __name__ == "__main__":
    unittest.main()
