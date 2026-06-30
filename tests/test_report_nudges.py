from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.presence_estimated import PresenceEstimatedResult
from core.report_nudges import (
    build_unanchored_anchors_nudge,
    build_unexplained_gap_nudge,
    unanchored_anchors_for_report,
)


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
        self.assertIn("gittan review", text)

    def test_nudge_hidden_when_gap_below_threshold(self):
        report = self._report(estimated=2.0, screen_hours=3.0)
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNone(text)

    def test_gap_nudge_suppressed_when_presence_estimate_shown(self):
        """Cursor-heavy days: Est. (presence) replaces observed-vs-screen alarm."""
        report = self._report(estimated=5.5, screen_hours=15.1)
        report.overall_days = {"2026-06-11": {"hours": 5.5}}
        report.screen_time_days = {"2026-06-11": 15.1 * 3600.0}
        report.presence_estimated = PresenceEstimatedResult(
            overall_days={"2026-06-11": 10.0},
            project_days={"project-alpha": {"2026-06-11": 10.0}},
            total_hours=10.0,
        )
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNone(text)

    def test_nudge_shown_for_uncategorized_only_case(self):
        report = self._report(estimated=4.0, screen_hours=4.0, uncategorized_hours=3.9)
        text = build_unexplained_gap_nudge(report, threshold_hours=1.5)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Uncategorized", text)
        self.assertIn("gittan review", text)

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


class UnanchoredAnchorsNudgeTests(unittest.TestCase):
    def _report(self, events, profiles):
        return SimpleNamespace(all_events=events, profiles=profiles)

    def test_lists_unanchored_dir_above_min_hits(self):
        events = [{"anchors": {"dir": "timelog-extract"}} for _ in range(30)]
        report = self._report(events, [{"name": "other", "match_terms": ["other"]}])
        anchors = unanchored_anchors_for_report(report, min_hits=20)
        self.assertEqual(anchors, [{"kind": "dir", "value": "timelog-extract", "hits": 30}])
        text = build_unanchored_anchors_nudge(report, min_hits=20)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("timelog-extract", text)
        self.assertIn("gittan map", text)

    def test_lists_unanchored_branch_and_label(self):
        events = (
            [{"anchors": {"branch": "project-beta"}} for _ in range(25)]
            + [{"anchors": {"label": "project beta redesign"}} for _ in range(22)]
        )
        report = self._report(events, [{"name": "other", "match_terms": ["other"]}])
        anchors = unanchored_anchors_for_report(report, min_hits=20)
        kinds = {a["kind"]: a["value"] for a in anchors}
        self.assertEqual(kinds, {"branch": "project-beta", "label": "project beta redesign"})
        # Sorted by hits descending across kinds.
        self.assertEqual(anchors[0]["kind"], "branch")

    def test_anchored_dir_is_not_nudged(self):
        events = [{"anchors": {"dir": "timelog-extract"}} for _ in range(30)]
        report = self._report(events, [{"name": "gittan", "match_terms": ["timelog-extract"]}])
        self.assertEqual(unanchored_anchors_for_report(report, min_hits=20), [])
        self.assertIsNone(build_unanchored_anchors_nudge(report, min_hits=20))

    def test_below_min_hits_is_not_nudged(self):
        events = [{"anchors": {"dir": "timelog-extract"}} for _ in range(5)]
        report = self._report(events, [{"name": "other", "match_terms": ["other"]}])
        self.assertEqual(unanchored_anchors_for_report(report, min_hits=20), [])

    def test_github_enriched_labels_are_not_map_nudges(self):
        """Delivery rows inherit session titles for display — not for gittan map."""
        events = [
            {
                "source": "GitHub",
                "anchors": {"label": "toggle integration progress"},
            }
            for _ in range(30)
        ]
        report = self._report(events, [{"name": "other", "match_terms": ["other"]}])
        self.assertEqual(unanchored_anchors_for_report(report, min_hits=20), [])


if __name__ == "__main__":
    unittest.main()
