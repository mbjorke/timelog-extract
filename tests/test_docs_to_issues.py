"""Tests for the docs → issues generator's pure parsing (no network/gh)."""

from __future__ import annotations

import unittest

from scripts.docs_to_issues import (
    MARKER,
    build_body,
    is_done,
    parse_task_prompt,
    refuses_promotion,
)

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
        self.assertTrue(is_done("verified"))  # template's final status (Qodo on #331)
        self.assertFalse(is_done("not built"))
        self.assertFalse(is_done("not verified"))
        self.assertFalse(is_done("in progress"))

    def test_is_done_negation_not_misclassified(self):
        # substring matching would wrongly flag these as done → they must stay open
        self.assertFalse(is_done("not done"))
        self.assertFalse(is_done("not yet implemented"))
        self.assertFalse(is_done("undone"))  # word-boundary: 'done' not a whole word here

    def test_is_done_built_and_released(self):
        # "built"/"released" are done states; #260/#261 leaked because "built" was missing
        self.assertTrue(is_done("built"))
        self.assertTrue(is_done("released"))
        self.assertFalse(is_done("rebuilt"))  # word-boundary: not "built" as a whole word

    def test_is_done_inline_backtick_value(self):
        # backtick-wrapped lead token must not hide a later done-word (toggl spec case)
        self.assertTrue(is_done("`now` items shipped"))

    def test_field_backtick_wrapped_value_not_truncated(self):
        # _field used to stop at the first backtick, dropping "shipped" → spec wrongly open
        it = parse_task_prompt(
            "# T\n## Traceability\n- implementation_status: `now` items shipped — Toggl push\n", "x"
        )
        self.assertEqual(it["impl_status"], "now items shipped — Toggl push")
        self.assertTrue(is_done(it["impl_status"]))

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


class RefusesPromotionTests(unittest.TestCase):
    """A spec can decline being turned into an issue (#567 review).

    Since 2026-08-18 an issue is opened when work starts, not when a pass
    prioritises it, so a planning artifact nobody has picked up has no issue by
    design. Promoting it anyway produces a ticket with no story id and no owner,
    and one spec has said 'do not promote' in prose since long before that rule,
    only to be proposed on every run.
    """

    def test_explicit_promote_no_is_honoured(self):
        block = "- story_id: `pending`\n- promote: no\n- spec_status: `draft`\n"
        self.assertTrue(refuses_promotion(block))

    def test_prose_refusal_is_honoured(self):
        block = (
            "- story_id: `pending` (do **not** promote via `/docs-to-issues` until a\n"
            "  later pass says so)\n"
        )
        self.assertTrue(refuses_promotion(block))

    def test_an_ordinary_spec_is_still_promotable(self):
        block = "- story_id: `GH-123`\n- spec_status: `approved`\n"
        self.assertFalse(refuses_promotion(block))

    def test_the_word_promote_alone_does_not_refuse(self):
        block = "- story_id: `GH-9`\n- changelog:\n  - 2026-01-01: promote to next.\n"
        self.assertFalse(refuses_promotion(block))

    def test_parsed_item_carries_the_flag(self):
        text = (
            "# Task Prompt: Example\n\n## Traceability\n\n"
            "- story_id: `pending` (do not promote yet)\n"
            "- implementation_status: `not built`\n"
        )
        self.assertTrue(parse_task_prompt(text, "example")["no_promote"])
