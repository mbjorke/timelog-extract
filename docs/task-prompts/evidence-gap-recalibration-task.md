# Recalibrate the Screen Time evidence-gap warning

## Backlog item

- **priority:** next (after GH-146 golden-eval telemetry-fixture gate; trust polish, not data-corrupting)
- **problem:** `core/evidence_diagnostics.py::build_evidence_warnings` warns
  `Large Screen Time gap (+{delta}h) suggests missing evidence` whenever
  `screen_time_hours - observed_hours >= 2.0`. The 2h threshold is a flat
  absolute value that does not scale with the report window, so on a monthly
  report it fires essentially always. It also labels *all* positive gap as
  "missing evidence", conflating three different causes:
  1. genuine work Gittan cannot see (real missing evidence → fixable via `review`/`map`),
  2. personal / non-work screen time (nothing to map),
  3. idle screen-on time.
- **user value:** The accuracy signals stop crying wolf, so a warning means
  something. Trust in the report's self-checks is the whole point of the
  accuracy net (see `docs/task-prompts/repo-time-totals-task.md`).
- **context / why now:** Screen Time = total device-on time; project work is
  always a subset, so `observed < Screen Time` is the *healthy* direction. The
  dangerous direction (`observed > Screen Time`, physically impossible =
  over-attribution) is already handled by the new `core/sanity_bounds.py`
  guardrail. This item is only about the *under-coverage* direction.
- **non-goals:**
  - Do not change session or billing math.
  - Do not try to classify the gap's cause perfectly — only avoid false alarms.
  - Do not remove the per-day "unexplained screen-time" nudge; align its framing
    in the same pass if cheap, but the report-level warning is the focus.

## Behavior

```gherkin
Feature: Honest Screen Time coverage warning
  The evidence gap warns only when project coverage is genuinely low,
  and never treats expected non-work screen time as missing evidence.

  Background:
    Given Screen Time measures total device-on time
    And observed hours measure project-attributed activity only

  Scenario: Healthy gap on a monthly report is not flagged
    Given a 30-day report with 110h observed and 149h Screen Time
    When the evidence check runs
    Then no "missing evidence" warning is shown
    And the gap is reported as informational coverage, not a problem

  Scenario: Genuinely low coverage is flagged
    Given a report where observed hours are below ~50% of Screen Time
    And there is mappable unattributed signal (unmapped hosts or anchors)
    When the evidence check runs
    Then a low-coverage warning points the user at "gittan review" / "gittan map"

  Scenario: Over-attribution is not this warning's job
    Given observed hours exceed Screen Time
    When the evidence check runs
    Then the under-coverage warning does not fire
    And the over-attribution guardrail (core/sanity_bounds.py) is responsible instead
```

## Acceptance criteria

- Threshold is a **fraction of Screen Time** (or scales with window length),
  not a flat 2h, so monthly reports with healthy gaps stay silent.
- The "missing evidence" wording is used only when there is mappable
  unattributed signal; otherwise the gap is framed as informational coverage.
- The two directions stay distinct: under-coverage here, over-attribution in
  `core/sanity_bounds.py`.
- Full autotest suite green; no Python file exceeds 500 lines.

## Validation

| Scenario | Evidence |
|---|---|
| Healthy monthly gap silent | Unit test: 110h observed / 149h screen, 30-day window → no warning |
| Genuinely low coverage flagged | Unit test: observed < 50% screen + unmapped signal → warning |
| Over-attribution not double-warned | Unit test: observed > screen → no under-coverage warning |

## Dependencies / open decisions

- **Open decision:** exact coverage threshold (fraction) and whether to scale by
  window length or by Screen Time magnitude.
- Reuses existing unmapped-host / unmapped-anchor signals to decide "mappable".

## Traceability

- story_id: (assign on pickup)
- spec_status: draft
- created_at: 2026-06-15
- related: GH-146 accuracy net (`core/sanity_bounds.py`, repo-time-totals-task.md)
