from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.presence_estimated import PresenceEstimatedResult
from core.report_nudges import (
    build_reattribution_nudge,
    build_title_workspace_conflict_nudge,
    build_unanchored_anchors_nudge,
    build_unexplained_gap_nudge,
    title_workspace_conflicts_for_report,
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
        self.assertNotIn("write-anchor-plan", text)
        self.assertIn("existing customer/line", text)

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
        text = build_unanchored_anchors_nudge(report, min_hits=20)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("session context", text)
        self.assertNotIn("write-anchor-plan", text)
        self.assertNotIn("projects-anchor", text.lower().replace("`", ""))
        # Soft mention of not promoting — avoid pointing at bulk apply.
        self.assertIn("match_terms", text)

    def test_anchored_dir_is_not_nudged(self):
        events = [{"anchors": {"dir": "timelog-extract"}} for _ in range(30)]
        report = self._report(events, [{"name": "gittan", "match_terms": ["timelog-extract"]}])
        self.assertEqual(unanchored_anchors_for_report(report, min_hits=20), [])
        self.assertIsNone(build_unanchored_anchors_nudge(report, min_hits=20))

    def test_below_min_hits_is_not_nudged(self):
        events = [{"anchors": {"dir": "timelog-extract"}} for _ in range(5)]
        report = self._report(events, [{"name": "other", "match_terms": ["other"]}])
        self.assertEqual(unanchored_anchors_for_report(report, min_hits=20), [])


class TitleWorkspaceConflictNudgeTests(unittest.TestCase):
    def test_conflict_nudge_above_min_hits(self):
        events = [
            {
                "project": "project-alpha",
                "anchors": {
                    "label": "project-alpha project update",
                    "project_from": "title",
                    "project_workspace": "project-beta",
                },
            }
            for _ in range(8)
        ]
        report = SimpleNamespace(all_events=events)
        conflicts = title_workspace_conflicts_for_report(report, min_hits=5)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["project"], "project-alpha")
        self.assertEqual(conflicts[0]["project_workspace"], "project-beta")
        text = build_title_workspace_conflict_nudge(report, min_hits=5)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("project-alpha", text)
        self.assertIn("project-beta", text)
        self.assertIn("Title was preferred", text)

    def test_conflict_nudge_hidden_below_min_hits(self):
        events = [
            {
                "project": "project-alpha",
                "anchors": {
                    "label": "project-alpha project update",
                    "project_from": "title",
                    "project_workspace": "project-beta",
                },
            }
            for _ in range(3)
        ]
        report = SimpleNamespace(all_events=events)
        self.assertEqual(title_workspace_conflicts_for_report(report, min_hits=5), [])
        self.assertIsNone(build_title_workspace_conflict_nudge(report, min_hits=5))

    def test_workspace_only_attribution_is_not_a_conflict(self):
        events = [
            {
                "project": "project-beta",
                "anchors": {
                    "label": "Generic refactor",
                    "project_from": "workspace",
                },
            }
            for _ in range(10)
        ]
        report = SimpleNamespace(all_events=events)
        self.assertIsNone(build_title_workspace_conflict_nudge(report, min_hits=5))


class ReattributionNudgeTests(unittest.TestCase):
    def _finding(self):
        return {
            "date": "2026-08-07",
            "moved": 1.21,
            "shift_share": 0.85,
            "net": -0.42,
            "losers": [{"project": "Alpha", "from": 1.65, "to": 0.02}],
            "gainers": [{"project": "Beta", "from": 4.60, "to": 5.81}],
        }

    def test_nudge_lists_movers_and_shift_share(self):
        text = build_reattribution_nudge(SimpleNamespace(), findings=[self._finding()])
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("re-attribution", text)
        self.assertIn("2026-08-07", text)
        self.assertIn("Alpha 1.65h → 0.02h", text)
        self.assertIn("Beta 4.60h → 5.81h", text)
        self.assertIn("shift share 85%", text)
        self.assertIn("keep-max", text)

    def test_nudge_keeps_gainers_when_many_losers(self):
        finding = self._finding()
        finding["losers"] = [
            {"project": f"Loser-{i}", "from": 1.0, "to": 0.0} for i in range(1, 5)
        ]
        finding["gainers"] = [{"project": "Beta", "from": 4.60, "to": 8.60}]
        text = build_reattribution_nudge(SimpleNamespace(), findings=[finding])
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Loser-1", text)
        self.assertIn("Loser-2", text)
        self.assertNotIn("Loser-3", text)
        self.assertIn("Beta 4.60h → 8.60h", text)

    def test_nudge_reads_report_attribute(self):
        report = SimpleNamespace(reattribution_vs_observed=[self._finding()])
        text = build_reattribution_nudge(report)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Alpha", text)

    def test_nudge_absent_without_findings(self):
        self.assertIsNone(build_reattribution_nudge(SimpleNamespace()))
        self.assertIsNone(build_reattribution_nudge(SimpleNamespace(reattribution_vs_observed=[])))


if __name__ == "__main__":
    unittest.main()
