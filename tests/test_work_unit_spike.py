"""Tests for work-unit v2 spike classifier and acceptance evaluator."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.work_unit_acceptance import (
    acceptance_from_dict,
    evaluate_spike,
    load_acceptance_file,
    parse_acceptance_markdown,
    slug_only_lines_created,
)
from core.work_unit_classifier import (
    build_work_units,
    classify_work_unit,
    customer_for_line,
    make_work_unit_classify_fn,
)

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "work_unit_acceptance.example.json"
)


def _profiles_with_thin_duplicate() -> list[dict]:
    return [
        {
            "name": "portal-engagement",
            "customer": "customer-a.example",
            "match_terms": [
                "portal-repo",
                "customer-a.example",
                "portal engagement",
                "acme/portal-repo",
            ],
            "tracked_urls": ["https://portal.customer-a.example"],
        },
        {
            "name": "portal-repo",
            "customer": "portal-repo",
            "match_terms": ["portal-repo"],
            "tracked_urls": [],
        },
        {
            "name": "faq-engagement",
            "customer": "customer-a.example",
            "match_terms": ["faq-app", "faq engagement"],
            "tracked_urls": [],
        },
    ]


class TestWorkUnitClassifier(unittest.TestCase):
    def test_build_collapses_thin_slug_into_canonical(self):
        units = build_work_units(_profiles_with_thin_duplicate())
        keys = {u.line_key for u in units}
        self.assertIn("portal-engagement", keys)
        self.assertIn("faq-engagement", keys)
        self.assertNotIn("portal-repo", keys)
        portal = next(u for u in units if u.line_key == "portal-engagement")
        self.assertEqual(portal.customer_ref, "customer-a.example")
        self.assertIn("portal-repo", portal.signals)
        self.assertIn("portal-repo", portal.source_names)

    def test_classify_maps_slug_evidence_to_canonical_line(self):
        units = build_work_units(_profiles_with_thin_duplicate())
        line = classify_work_unit(
            "working in /Users/dev/Workspace/acme/portal-repo on a fix",
            units,
            "Uncategorized",
        )
        self.assertEqual(line, "portal-engagement")
        self.assertEqual(
            customer_for_line(units, line),
            "customer-a.example",
        )

    def test_classify_fn_seam_matches_profiles_shape(self):
        classify = make_work_unit_classify_fn("Uncategorized")
        profiles = _profiles_with_thin_duplicate()
        self.assertEqual(
            classify("checkout faq-app docs", profiles),
            "faq-engagement",
        )
        self.assertEqual(
            classify("random noise with no anchors", profiles),
            "Uncategorized",
        )

    def test_customer_never_inferred_from_signal_alone(self):
        """Winning unit's customer_ref comes from the profile, not the matched term."""
        units = build_work_units(_profiles_with_thin_duplicate())
        line = classify_work_unit("portal-repo commit", units, "Uncategorized")
        self.assertEqual(line, "portal-engagement")
        self.assertEqual(customer_for_line(units, line), "customer-a.example")
        self.assertNotEqual(customer_for_line(units, line), "portal-repo")


class TestWorkUnitAcceptance(unittest.TestCase):
    def test_load_example_fixture(self):
        table = load_acceptance_file(FIXTURE)
        self.assertEqual(table.date_from, "2026-06-01")
        self.assertEqual(len(table.lines), 2)
        self.assertEqual(table.lines[0].customer, "customer-a.example")

    def test_parse_markdown_table(self):
        md = """
date_from: 2026-06-01
date_to: 2026-06-30
tolerance_hours: 0.5
primary_uncategorized_max: 1.0

| Customer | Line | Hours |
| --- | --- | --- |
| customer-a.example | portal-engagement | 8.0 |
| customer-a.example | faq-engagement | 2.0h |
"""
        table = parse_acceptance_markdown(md)
        self.assertEqual(table.primary_uncategorized_max, 1.0)
        self.assertEqual(table.lines[1].expected_hours, 2.0)

    def test_evaluate_go_when_within_tolerance(self):
        acceptance = acceptance_from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
        report = SimpleNamespace(
            project_reports={
                "portal-engagement": {"2026-06-02": {"hours": 8.1}},
                "faq-engagement": {"2026-06-03": {"hours": 1.9}},
                "Uncategorized": {"2026-06-04": {"hours": 0.2}},
            },
            profiles=_profiles_with_thin_duplicate(),
        )
        verdict = evaluate_spike(report, acceptance, profiles=report.profiles)
        self.assertEqual(verdict.decision, "GO")
        self.assertTrue(verdict.no_slug_only_created)

    def test_evaluate_nogo_on_slug_only_hours(self):
        acceptance = acceptance_from_dict(
            {
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
                "tolerance_hours": 5.0,
                "primary_uncategorized_max": 10.0,
                "lines": [],
            }
        )
        # Simulate v1 report where thin slug still owns hours.
        report = SimpleNamespace(
            project_reports={
                "portal-repo": {"2026-06-02": {"hours": 3.0}},
                "Uncategorized": {},
            },
            profiles=_profiles_with_thin_duplicate(),
        )
        offenders = slug_only_lines_created(report.profiles, {"portal-repo": 3.0})
        self.assertEqual(offenders, ["portal-repo"])
        verdict = evaluate_spike(report, acceptance, profiles=report.profiles)
        self.assertEqual(verdict.decision, "NO-GO")
        self.assertFalse(verdict.no_slug_only_created)

    def test_evaluate_nogo_when_uncategorized_too_high(self):
        acceptance = acceptance_from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
        report = SimpleNamespace(
            project_reports={
                "portal-engagement": {"2026-06-02": {"hours": 8.0}},
                "faq-engagement": {"2026-06-03": {"hours": 2.0}},
                "Uncategorized": {"2026-06-04": {"hours": 4.0}},
            },
            profiles=_profiles_with_thin_duplicate(),
        )
        verdict = evaluate_spike(report, acceptance, profiles=report.profiles)
        self.assertEqual(verdict.decision, "NO-GO")
        self.assertFalse(verdict.uncategorized_ok)


class TestAttributionClassifierOption(unittest.TestCase):
    def test_resolve_work_unit_classifier(self):
        from core.work_unit_classifier import resolve_attribution_classify_fn

        fn = resolve_attribution_classify_fn("work_unit_v2", fallback="Uncategorized")
        profiles = _profiles_with_thin_duplicate()
        self.assertEqual(fn("portal-repo work", profiles), "portal-engagement")

    def test_default_remains_v1(self):
        from core.domain import classify_project
        from core.work_unit_classifier import resolve_attribution_classify_fn

        fn = resolve_attribution_classify_fn(
            "v1",
            fallback="Uncategorized",
            v1_fn=lambda text, profiles: classify_project(text, profiles, "Uncategorized"),
        )
        profiles = _profiles_with_thin_duplicate()
        # v1 still prefers the thin slug profile when it matches first by score.
        result = fn("portal-repo only", profiles)
        self.assertIn(result, {"portal-repo", "portal-engagement"})


if __name__ == "__main__":
    unittest.main()
