"""Tests for the docs → issues generator's pure parsing (no network/gh)."""

from __future__ import annotations

import unittest

from scripts.docs_to_issues import MARKER, build_body, is_done, parse_task_prompt

SPEC = """# Work-unit v2 attribution

Intro prose.

## Traceability

- story_id: `GH-222`
- spec_status: `draft`
- implementation_status: `not built`

## Behavior Contract

```gherkin
Feature: Attribution
  Scenario: pick a line
    Given a gap
    Then it maps to a line
```
"""


class DocsToIssuesParseTests(unittest.TestCase):
    def test_parses_title_traceability_and_gherkin(self):
        it = parse_task_prompt(SPEC, "work-unit-v2")
        self.assertEqual(it["title"], "Work-unit v2 attribution")
        self.assertEqual(it["story_id"], "GH-222")
        self.assertEqual(it["spec_status"], "draft")
        self.assertEqual(it["impl_status"], "not built")
        self.assertEqual(len(it["gherkin"]), 1)
        self.assertIn("Scenario: pick a line", it["gherkin"][0])

    def test_plain_unbackticked_fields(self):
        it = parse_task_prompt("# T\n## Traceability\n- story_id: GH-9\n- implementation_status: in progress\n")
        self.assertEqual(it["story_id"], "GH-9")
        self.assertEqual(it["impl_status"], "in progress")

    def test_is_done_detection(self):
        self.assertTrue(is_done("shipped"))
        self.assertTrue(is_done("Done — merged in #212"))
        self.assertFalse(is_done("not built"))
        self.assertFalse(is_done("in progress"))

    def test_is_done_negation_not_misclassified(self):
        # substring matching would wrongly flag these as done → they must stay open
        self.assertFalse(is_done("not done"))
        self.assertFalse(is_done("not yet implemented"))
        self.assertFalse(is_done("undone"))  # word-boundary: 'done' not a whole word here

    def test_build_body_includes_traceability_without_story(self):
        it = parse_task_prompt("# T\n## Traceability\n- implementation_status: in progress\n", "x")
        body = build_body(it, "docs/task-prompts/x.md")
        self.assertIn("**Story:** —", body)
        self.assertIn("impl: in progress", body)
        self.assertIn(f"<!-- {MARKER}: docs/task-prompts/x.md -->", body)

    def test_build_body_has_marker_and_acceptance(self):
        it = parse_task_prompt(SPEC, "x")
        body = build_body(it, "docs/task-prompts/x.md")
        self.assertIn(f"<!-- {MARKER}: docs/task-prompts/x.md -->", body)
        self.assertIn("## Acceptance criteria", body)
        self.assertIn("GH-222", body)

    def test_missing_traceability_is_safe(self):
        it = parse_task_prompt("# Only a title\n\nSome prose, no traceability.", "stem")
        self.assertEqual(it["title"], "Only a title")
        self.assertEqual(it["story_id"], "")
        self.assertEqual(it["gherkin"], [])


if __name__ == "__main__":
    unittest.main()
