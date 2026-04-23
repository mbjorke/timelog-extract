"""Unit tests for helper functions in scripts/calibration/run_month_end_invoice_check.py."""

import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Stub out heavyweight dependencies so the script module can be imported
# in test environments that don't have the full runtime (typer, rich, etc.)
_stubs = {}
for mod_name in [
    "typer",
    "rich",
    "rich.console",
    "rich.table",
    "rich.text",
    "questionary",
    "core.cli",
    "core.report_service",
]:
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        stub.TimelogRunOptions = MagicMock
        stub.run_timelog_report = MagicMock()
        sys.modules[mod_name] = stub
        _stubs[mod_name] = stub

# Now import the helpers from the script
from scripts.calibration.run_month_end_invoice_check import (  # noqa: E402
    _markdown,
    _project_hours,
    _top_deltas,
)


class ProjectHoursTests(unittest.TestCase):
    """Tests for _project_hours helper."""

    def _make_report(self, project_reports: dict):
        """Build a minimal report-like object."""
        return SimpleNamespace(project_reports=project_reports)

    def test_basic_extraction(self):
        """Extracts and sums hours from project_reports correctly."""
        report = self._make_report({
            "ProjectA": {"2026-03-01": {"hours": 2.0}, "2026-03-02": {"hours": 3.0}},
            "ProjectB": {"2026-03-01": {"hours": 1.5}},
        })
        result = _project_hours(report)
        self.assertAlmostEqual(result["ProjectA"], 5.0)
        self.assertAlmostEqual(result["ProjectB"], 1.5)

    def test_empty_project_reports_returns_empty_dict(self):
        """Empty project_reports returns empty dict."""
        report = self._make_report({})
        self.assertEqual(_project_hours(report), {})

    def test_hours_rounded_to_six_decimal_places(self):
        """Hours are rounded to 6 decimal places."""
        report = self._make_report({
            "P": {"d": {"hours": 1.123456789}}
        })
        result = _project_hours(report)
        self.assertEqual(result["P"], round(1.123456789, 6))

    def test_missing_hours_key_treated_as_zero(self):
        """Day entries without 'hours' key contribute 0.0."""
        report = self._make_report({
            "P": {"d": {}}
        })
        result = _project_hours(report)
        self.assertAlmostEqual(result["P"], 0.0)

    def test_single_day_project(self):
        """Single-day project hours are extracted correctly."""
        report = self._make_report({
            "Solo": {"2026-03-15": {"hours": 7.25}},
        })
        result = _project_hours(report)
        self.assertAlmostEqual(result["Solo"], 7.25)

    def test_project_name_is_string(self):
        """Project keys in the result are always strings."""
        report = self._make_report({"P": {"d": {"hours": 1.0}}})
        result = _project_hours(report)
        for key in result:
            self.assertIsInstance(key, str)


class TopDeltasTests(unittest.TestCase):
    """Tests for _top_deltas helper."""

    def test_basic_delta_calculation(self):
        """Computes the correct delta between current and previous hours."""
        current = {"ProjA": 5.0, "ProjB": 2.0}
        previous = {"ProjA": 3.0, "ProjB": 2.0}
        result = _top_deltas(current, previous)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["project"], "ProjA")
        self.assertAlmostEqual(result[0]["delta_hours"], 2.0)

    def test_zero_delta_excluded(self):
        """Projects with no change are excluded from results."""
        current = {"P": 1.0}
        previous = {"P": 1.0}
        result = _top_deltas(current, previous)
        self.assertEqual(result, [])

    def test_sorted_by_absolute_delta_descending(self):
        """Results are sorted by absolute delta descending."""
        current = {"A": 10.0, "B": 3.0, "C": 0.5}
        previous = {"A": 8.0, "B": 1.0, "C": 0.0}
        result = _top_deltas(current, previous)
        deltas = [abs(float(r["delta_hours"])) for r in result]
        self.assertEqual(deltas, sorted(deltas, reverse=True))

    def test_limit_respected(self):
        """Result is limited to the specified limit."""
        current = {f"P{i}": float(i + 1) for i in range(20)}
        previous = {}
        result = _top_deltas(current, previous, limit=5)
        self.assertEqual(len(result), 5)

    def test_default_limit_is_8(self):
        """Default limit is 8."""
        current = {f"P{i}": float(i + 1) for i in range(15)}
        previous = {}
        result = _top_deltas(current, previous)
        self.assertEqual(len(result), 8)

    def test_new_project_in_current_only(self):
        """Project appearing only in current is treated as delta from 0."""
        current = {"New": 3.0}
        previous = {}
        result = _top_deltas(current, previous)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["project"], "New")
        self.assertAlmostEqual(result[0]["current_hours"], 3.0)
        self.assertAlmostEqual(result[0]["previous_hours"], 0.0)

    def test_project_missing_from_current(self):
        """Project appearing only in previous has negative delta."""
        current = {}
        previous = {"Removed": 4.0}
        result = _top_deltas(current, previous)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["delta_hours"], -4.0)

    def test_empty_inputs_returns_empty(self):
        """Empty current and previous dicts return empty list."""
        self.assertEqual(_top_deltas({}, {}), [])

    def test_near_zero_delta_excluded(self):
        """Delta smaller than 1e-9 is treated as zero and excluded."""
        current = {"P": 1.000000000001}
        previous = {"P": 1.0}
        result = _top_deltas(current, previous)
        self.assertEqual(result, [])

    def test_result_rows_have_required_keys(self):
        """Each result row contains project, current_hours, previous_hours, delta_hours."""
        current = {"P": 5.0}
        previous = {"P": 2.0}
        result = _top_deltas(current, previous)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertIn("project", row)
        self.assertIn("current_hours", row)
        self.assertIn("previous_hours", row)
        self.assertIn("delta_hours", row)


class MarkdownTests(unittest.TestCase):
    """Tests for _markdown output generator."""

    def _minimal_payload(self):
        return {
            "range": {"from": "2026-03-01", "to": "2026-03-31"},
            "invoice_mode": "calibrated-a",
            "ground_truth_path": "/path/to/truth.json",
            "report_total_hours": 97.5,
            "ground_truth_total_hours": 100.0,
        }

    def test_returns_string(self):
        """_markdown returns a string."""
        result = _markdown(self._minimal_payload())
        self.assertIsInstance(result, str)

    def test_contains_heading(self):
        """Output contains markdown heading."""
        result = _markdown(self._minimal_payload())
        self.assertIn("# Month-end invoice check", result)

    def test_contains_date_range(self):
        """Output contains the date range from the payload."""
        result = _markdown(self._minimal_payload())
        self.assertIn("2026-03-01", result)
        self.assertIn("2026-03-31", result)

    def test_contains_invoice_mode(self):
        """Output contains the invoice mode."""
        result = _markdown(self._minimal_payload())
        self.assertIn("calibrated-a", result)

    def test_contains_report_total_hours(self):
        """Output contains the report total hours formatted to 3 decimal places."""
        result = _markdown(self._minimal_payload())
        self.assertIn("97.500h", result)

    def test_contains_ground_truth_total_hours(self):
        """Output contains the ground truth total hours."""
        result = _markdown(self._minimal_payload())
        self.assertIn("100.000h", result)

    def test_no_previous_day_section_when_absent(self):
        """No end-date sanity section when previous_day_comparison is absent."""
        result = _markdown(self._minimal_payload())
        self.assertNotIn("End-date sanity check", result)

    def test_previous_day_section_when_present(self):
        """End-date sanity section appears when previous_day_comparison is provided."""
        payload = self._minimal_payload()
        payload["previous_day_comparison"] = {
            "range_to": "2026-03-30",
            "previous_total_hours": 90.0,
            "delta_hours": 7.5,
            "top_project_deltas": [],
        }
        result = _markdown(payload)
        self.assertIn("End-date sanity check", result)
        self.assertIn("90.000h", result)
        self.assertIn("+7.500h", result)

    def test_top_project_deltas_listed(self):
        """Top project deltas are listed when provided."""
        payload = self._minimal_payload()
        payload["previous_day_comparison"] = {
            "range_to": "2026-03-30",
            "previous_total_hours": 90.0,
            "delta_hours": 7.5,
            "top_project_deltas": [
                {
                    "project": "BigProject",
                    "delta_hours": 5.0,
                    "previous_hours": 20.0,
                    "current_hours": 25.0,
                }
            ],
        }
        result = _markdown(payload)
        self.assertIn("BigProject", result)
        self.assertIn("+5.000h", result)

    def test_ends_with_newline(self):
        """Output always ends with a newline."""
        result = _markdown(self._minimal_payload())
        self.assertTrue(result.endswith("\n"))

    def test_ground_truth_path_in_output(self):
        """The ground truth file path appears in the output."""
        result = _markdown(self._minimal_payload())
        self.assertIn("/path/to/truth.json", result)


if __name__ == "__main__":
    unittest.main()