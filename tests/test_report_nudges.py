from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.report_nudges import build_unexplained_gap_nudge


class ReportNudgesTests(unittest.TestCase):
    def _report(self, estimated: float, screen_hours: float, uncategorized_hours: float = 0.0):
        project_reports = {}
        if uncategorized_hours > 0:
            project_reports["Uncategorized"] = {"2026-04-30": {"hours": uncategorized_hours}}
        return SimpleNamespace(
            overall_days={"2026-04-30": {"hours": estimated}},
            screen_time_days={"2026-04-30": screen_hours * 3600.0},
            project_reports=project_reports,
        )

    def test_nudge_shown_when_gap_above_threshold(self):
        report = self._report(estimated=1.0, screen_hours=3.0)
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("evidence-check", text)
        self.assertIn("triage-guided", text)

    def test_nudge_hidden_when_gap_below_threshold(self):
        report = self._report(estimated=2.0, screen_hours=3.0)
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNone(text)

    def test_nudge_shown_for_uncategorized_only_case(self):
        report = self._report(estimated=4.0, screen_hours=4.0, uncategorized_hours=3.9)
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Uncategorized", text)
        self.assertIn("triage-guided", text)

    def test_uncategorized_nudge_suppressed_when_residual_noise_dominates(self):
        report = self._report(estimated=4.0, screen_hours=4.0, uncategorized_hours=3.9)
        report.included_events = [
            {
                "project": "Uncategorized",
                "day": "2026-04-30",
                "detail": "https://cursor.com/changelog canvas sdk mirror failed",
            },
            {
                "project": "Uncategorized",
                "day": "2026-04-30",
                "detail": "https://cursor.sh/docs cursor diagnostics",
            },
            {
                "project": "Uncategorized",
                "day": "2026-04-30",
                "detail": "https://cursor.com/features skills-cursor",
            },
            {
                "project": "Uncategorized",
                "day": "2026-04-30",
                "detail": "https://cursor.sh/pricing mcp tool schema",
            },
            {
                "project": "Uncategorized",
                "day": "2026-04-30",
                "detail": "https://example.com/real-work",
            },
        ]
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()
