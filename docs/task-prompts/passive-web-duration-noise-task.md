# Passive web duration noise — Chrome / Claude.ai / Gemini (web)

Spec: `docs/specs/source-evidence-policy.md` (Chrome and tracked web URLs are
`passive_context`; good for classification, weak for duration).

## Problem

Chrome visit timestamps reflect navigation/refresh, not active work. Long-lived
tabs produce repeat visits (including overnight). Gittan inflated this into many
short sessions with minimum floors (0.1–0.25 h), adding hundreds of observed
hours YTD from tab noise alone.

## Scope (slice 1 — built)

- Reclassify `Claude.ai (web)` and `Gemini (web)` as `passive_context`; remove
  from `AI_SOURCES`.
- Apply calendar-day dedupe (`thin_chrome_visit_rows_by_day`: one visit per
  normalized URL per UTC day) to Claude.ai (web) and Gemini (web) collectors.
- Sessions where **all** sources are `passive_context`: duration floor **0**
  (still visible for classification/review).

## Non-goals (later)

- Corroboration gate (web duration only when IDE/worklog nearby).
- Separate `--web-collapse-minutes` CLI flag (web dedupe toggle vs Chrome rolling window).
- Re-run full-year before/after report in CI.

## Acceptance

```gherkin
Feature: Passive web visits do not inflate observed hours

  Scenario: Passive-only Chrome session contributes zero hours
    Given a session with only Chrome events and zero wall-clock span
    When hours are estimated
    Then the session duration should be 0.0h

  Scenario: Same chat URL revisits within a day collapse to one event
    Given two Claude.ai visits to the same normalized URL on the same calendar day
    When Claude.ai (web) is collected with default collapse
    Then only one event should be emitted for that URL that day

  Scenario: Same chat URL revisits on different UTC days stay separate
    Given two Claude.ai visits to the same normalized URL ten minutes apart across UTC midnight
    When Claude.ai (web) is collected with default collapse
    Then one event should be emitted for each UTC calendar day

  Scenario: Mixed Cursor and Claude.ai session keeps AI floor
    Given a session with Cursor and Claude.ai (web) events
    When hours are estimated with a 1-minute wall span
    Then the session should use the AI minimum floor
```

## Traceability

- story_id: GH-164
- spec_status: approved
- implementation_status: built
- created_at: 2026-06-23
- last_updated_at: 2026-06-23
- implementation.pr: pending
- implementation.branch: task/report-postamble-spinner
- implementation.commits: []
- validation.evidence: tests/test_core_domain.py, tests/test_chrome_web_collapse.py
- validation.decision: conditional GO
- changelog:
  - 2026-06-23: Calendar-day web dedupe (CodeRabbit #166); midnight boundary test.
  - 2026-06-23: Slice 1 implemented after YTD Chrome noise analysis in maintainer session.
