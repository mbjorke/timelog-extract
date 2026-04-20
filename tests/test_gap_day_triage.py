from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.calibration.gap_day_triage import (
    DayTopSite,
    apply_domain_mappings,
    day_gap_row,
    load_gap_payload,
    parse_map_assignments,
    render_report,
    score_projects_for_sites,
    summarize_day_sites,
)


class GapDayTriageTests(unittest.TestCase):
    def test_load_gap_payload_requires_days_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gap.json"
            path.write_text('{"totals": {}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_gap_payload(path)

    def test_day_gap_row_finds_requested_day(self):
        payload = {"days": [{"day": "2026-04-02", "unexplained_screen_time_hours": 2.0}]}
        row = day_gap_row(payload, "2026-04-02")
        self.assertEqual(row["day"], "2026-04-02")
        with self.assertRaises(ValueError):
            day_gap_row(payload, "2026-04-03")

    def test_summarize_day_sites_aggregates_domains(self):
        rows = [
            (1, "https://github.com/mbjorke/timelog-extract", "Repo"),
            (2, "https://github.com/mbjorke/briox-buddy", "PR"),
            (3, "https://www.notion.so/workspace", "Notion"),
        ]
        sites = summarize_day_sites(rows, limit=5)
        self.assertEqual(sites[0].domain, "github.com")
        self.assertEqual(sites[0].visits, 2)
        self.assertEqual(len(sites), 2)

    def test_score_projects_rolls_up_to_canonical_project(self):
        profiles = [
            {
                "name": "timelog-extract",
                "canonical_project": "Gittan",
                "aliases": ["timelog-extract", "briox-buddy"],
                "tracked_urls": ["github.com/mbjorke/timelog-extract"],
                "match_terms": [],
            },
            {
                "name": "briox-buddy",
                "canonical_project": "Gittan",
                "aliases": ["timelog-extract", "briox-buddy"],
                "tracked_urls": ["github.com/mbjorke/briox-buddy"],
                "match_terms": [],
            },
            {"name": "Beta", "canonical_project": "Beta", "aliases": ["Beta"], "tracked_urls": [], "match_terms": ["notion"]},
        ]
        top_sites = [
            DayTopSite(domain="github.com", visits=3, share=0.6, sample_title="Repo"),
            DayTopSite(domain="notion.so", visits=2, share=0.4, sample_title="Notes"),
        ]
        scores = score_projects_for_sites(profiles, top_sites)
        self.assertEqual(scores[0][0], "Gittan")
        self.assertIn("briox-buddy", scores[0][2])
        self.assertGreater(scores[0][1], scores[1][1])

    def test_render_report_includes_next_action_hint(self):
        report = render_report(
            day="2026-04-02",
            gap_row={
                "estimated_hours": 1.0,
                "screen_time_hours": 2.0,
                "unexplained_screen_time_hours": 1.0,
            },
            top_sites=[DayTopSite(domain="github.com", visits=3, share=1.0, sample_title="Repo")],
            project_suggestions=[("Gittan", 9, ["timelog-extract", "briox-buddy"])],
            projects_config="timelog_projects.json",
        )
        self.assertIn("Gap Day Triage (Internal)", report)
        self.assertIn("github.com", report)
        self.assertIn("aliases: timelog-extract, briox-buddy", report)
        self.assertIn("gittan suggest-rules --project \"Gittan\" --from 2026-04-02 --to 2026-04-02", report)

    def test_parse_map_assignments_accepts_domain_project_pairs(self):
        parsed = parse_map_assignments(["github.com=Gittan", "notion.so=ClientA"])
        self.assertEqual(parsed[0], ("github.com", "Gittan"))
        self.assertEqual(parsed[1], ("notion.so", "ClientA"))
        with self.assertRaises(ValueError):
            parse_map_assignments(["missing-separator"])

    def test_apply_domain_mappings_writes_tracked_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            config_path.write_text(
                (
                    "{\n"
                    '  "projects": [\n'
                    '    {"name":"Gittan","match_terms":["gittan"],"tracked_urls":[]}\n'
                    "  ]\n"
                    "}\n"
                ),
                encoding="utf-8",
            )
            applied_count, created_count = apply_domain_mappings(
                config_path,
                [("github.com", "Gittan"), ("example.com", "NewProject")],
                allow_create_projects=True,
            )
            self.assertEqual(applied_count, 2)
            self.assertEqual(created_count, 1)
            text = config_path.read_text(encoding="utf-8")
            self.assertIn("github.com", text)
            self.assertIn("example.com", text)

    def test_apply_domain_mappings_rejects_unknown_projects_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            config_path.write_text(
                (
                    "{\n"
                    '  "projects": [\n'
                    '    {"name":"Gittan","match_terms":["gittan"],"tracked_urls":[]}\n'
                    "  ]\n"
                    "}\n"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                apply_domain_mappings(
                    config_path,
                    [("github.com", "MissingProject")],
                )

    def test_generic_domain_is_downweighted_without_explicit_mapping(self):
        profiles = [
            {
                "name": "ProjectA",
                "canonical_project": "ProjectA",
                "aliases": ["ProjectA"],
                "tracked_urls": [],
                "match_terms": ["github"],
            },
            {
                "name": "ProjectB",
                "canonical_project": "ProjectB",
                "aliases": ["ProjectB"],
                "tracked_urls": ["internal.example.com"],
                "match_terms": ["internal"],
            },
        ]
        top_sites = [
            DayTopSite(domain="github.com", visits=100, share=0.7, sample_title="GH"),
            DayTopSite(domain="internal.example.com", visits=20, share=0.3, sample_title="Internal"),
        ]
        scores = score_projects_for_sites(profiles, top_sites)
        self.assertEqual(scores[0][0], "ProjectB")

    def test_explicit_mapped_domain_beats_generic_overlap(self):
        profiles = [
            {
                "name": "Mapped",
                "canonical_project": "Mapped",
                "aliases": ["Mapped"],
                "tracked_urls": ["github.com"],
                "match_terms": [],
            },
            {
                "name": "TermOnly",
                "canonical_project": "TermOnly",
                "aliases": ["TermOnly"],
                "tracked_urls": [],
                "match_terms": ["github"],
            },
        ]
        top_sites = [DayTopSite(domain="github.com", visits=30, share=1.0, sample_title="GH")]
        scores = score_projects_for_sites(profiles, top_sites)
        self.assertEqual(scores[0][0], "Mapped")


if __name__ == "__main__":
    unittest.main()
