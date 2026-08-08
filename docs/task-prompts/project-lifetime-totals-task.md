# Total time per project: the gate is already met, and the storage is not config

A product-owner pass on bringing back per-project lifetime totals. It corrects
two premises, finds the blocking gate satisfied, and separates the withdrawn
column from the larger feature it is usually confused with.

No code in this pass.

## Traceability

- story_id: `GH-536` · all-source slice = `GH-537`
- spec_status: approved
- implementation_status: not built (planning artifact — no code)
- created_at: 2026-08-08
- last_updated_at: 2026-08-08
- implementation.pr: pending
- implementation.branch: `task/project-lifetime-totals`
- implementation.commits: []
- validation.evidence:
  - `core/sanity_bounds.py` + `tests/test_sanity_bounds.py` present (11 tests)
  - `scripts/run_golden_eval.py --check` runs 4 datasets including
    `tests/fixtures/golden_cursor_composer_dataset.json`, whose invariants pin
    the day-collapse class; executed by `tests/test_golden_eval.py`, which runs
    in `scripts/run_autotests.sh` and therefore in CI
  - `core/timelog_totals.py` intact; `core/report_service.py:359` holds the
    withdrawal stub
- validation.decision: GO
- changelog:
  - 2026-08-08: Second correction. Reframed the store as durability rather than
    performance (logs rotate; the answer must survive), withdrew the
    `--screen-time off` question as mis-posed since Screen Time contributes no
    hours, and closed #536 once the TIMELOG retirement in #408 made it a surface
    on replaced storage.
  - 2026-08-08: Corrected after learning the requester's setup — 82 profiles and
    no worklog. Swapped the priorities: the worklog-only column cannot serve him
    and drops to `later`; all-source totals become the `now` item. Measured the
    aggregation cost (about a second for a year at 82 profiles), which removes
    the caching question entirely.
  - 2026-08-08: Initial pass.

Labels are the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`).

---

## Who asked, and what they actually need

The requirement came from the beta tester: total time per project, quickly, on an
installation with **82 project profiles**. He keeps using Gittan only if it gives
immediate value, which makes "quickly" part of the requirement rather than a
nicety.

That reframes everything below, and it invalidated this pass's first draft. The
withdrawn column is **worklog-only**, and his installation has no worklog at all —
`doctor` reports it as not found. A worklog-only lifetime column would have shown
him 82 empty cells under a heading promising lifetime hours, which is worse than
shipping nothing: it spends the one thing he is short of, patience with a tool
that has not paid off yet.

The error was reaching for the cheapest unblocked thing once the accuracy gate
turned out to be satisfied, instead of the thing that was asked for.

## Two premises worth correcting first

**The column was not removed for being slow.** It was removed for trust. The
product-owner decision recorded in `docs/task-prompts/repo-time-totals-task.md`
is explicit: beta testing exposed a catastrophic accuracy regression where whole
days collapsed into single ~24h sessions, and the withdrawn column — which is
**worklog-only** — then read *lower* than the inflated period `Hours` column.
Two contradictory numbers side by side erode trust, so the least-corrupted
column was the one withdrawn. Performance is not mentioned anywhere in that
decision, and the aggregation code was deliberately left in place "for easy
re-introduction".

That matters, because a fix aimed at speed would not address why it was pulled.

**The gate has already been met.** Re-introduction was gated on two items:

| Gate | State |
| --- | --- |
| Sanity-bound guardrails | **done** — `core/sanity_bounds.py`, 11 tests |
| Golden eval catches the day-collapse class | **done** — `golden_cursor_composer_dataset.json` runs in CI with `max_hours_any_day`, `max_day_total_hours`, `max_period_total_hours` invariants |

Both were satisfied, and the column stayed withdrawn because nobody rechecked
the gate. That is the same shape as the other findings this week: a condition is
met, nothing announces it, and the state persists by default. Worth a habit, not
just a fix — when a decision is gated, the gate needs an owner.

## Why the total does not belong in the project config

The proposal on the table is that each project's config entry tracks that
project's lifetime total, so the column can be cheap. It should not, for four
reasons that compound:

1. **Config is a declaration a human made.** #406 exists specifically to stop
   automated writes to `timelog_projects.json`, and `GH-526` builds on the same
   line: a report derives, it does not write config. A running total written by
   the reporting path makes config derived state and breaks that boundary at its
   most load-bearing point.
2. **A stored number is a number you have to trust.** The product's claim is that
   every figure traces to inspectable evidence. A cached total that drifts from
   the events is exactly the failure the withdrawn column was pulled for: two
   numbers that disagree, and no way to tell which is right.
3. **It merges badly.** Two devices each holding a running total cannot be
   reconciled by git, and device portability is already an open question with
   unresolved merge semantics.
4. **The derived store already exists.** `observed/*.jsonl` has keep-max
   semantics, is versioned, and is where derived aggregates belong. Adding a
   second, weaker cache in config would leave two sources of truth.

If a cache turns out to be needed, its home is the evidence store, and it must
be reconstructible from events by deleting it.

**It turns out none is needed.** Measured at the tester's profile count, with
synthetic events in collector shape:

| Profiles | Days | Events | Classify | Session math | Total |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 82 | 30 | 6,000 | 0.08s | 0.00s | **0.09s** |
| 82 | 180 | 36,000 | 0.53s | 0.02s | **0.55s** |
| 82 | 365 | 73,000 | 1.16s | 0.04s | **1.20s** |
| 10 | 365 | 73,000 | 0.25s | 0.04s | 0.29s |

A full year at 82 profiles aggregates in about a second. Summing is free — 0.04s
at 73,000 events. The cost is **classification**, which scales with profile count
rather than with the totals feature: 8.2× the profiles costs 4.6× the time at
identical event volume.

So the objections above stop being load-bearing and become moot: there is nothing
worth caching. And if lifetime totals ever feel slow, the cost is **collection**,
not computation — re-reading every log and SQLite store for all time. That points
at aggregating from the `observed/` store, which is already on disk and already
keep-max, rather than from a fresh collection run.

## What is actually two different features

The withdrawn column and "total time for a project" are usually spoken of as one
thing. They are not, and conflating them is why the ask keeps stalling.

| | Withdrawn column | Lifetime totals |
| --- | --- | --- |
| Sources | worklog only (`TIMELOG.md`) | all sources |
| Span | all time | all time |
| Cost | cheap — one file parse | scales with retained evidence |
| Blocked by | nothing, as of the gate check above | a storage decision |

The first can come back now. The second is the one where performance is a real
question, and where the storage decision has to be made honestly rather than by
reaching for config because it is nearby.

---

## Backlog

### Bring back the worklog lifetime column, with an honest label

- priority: **do not build** (#536 closed). It does not answer the ask: it is
  blank for the installation that requested the feature. It also reads
  `TIMELOG.md` exclusively, and #408 is moving that storage to the shadow log
  with markdown as a view, so this would build a new surface on the file being
  replaced. The aggregation code can stay; nothing depends on removing it.
- problem: the column was withdrawn under a condition that no longer holds, and
  the aggregation was deliberately kept intact for this moment.
- user value: the sanity check the beta tester originally asked for — "does this
  project really only have ten hours on it?"
- non-goals: all-source totals, invoiced totals, any new storage.
- behavior: the column returns, and it says what it is. The original trust
  failure was not the number, it was a label that invited comparison with a
  differently-sourced column. A worklog-derived lifetime figure next to an
  all-source period figure is only confusing while it pretends to be comparable.

```gherkin
Feature: Lifetime worklog hours are visible again

  Scenario: The column states its source
    Given a project with worklog history outside the report period
    When the operator runs `gittan status`
    Then a lifetime column shows the worklog-derived total
    And its label identifies it as worklog-derived, not all-source
    And it is not presented as comparable to the period Hours column

  Scenario: A project with no worklog history
    Given a project that has never appeared in a worklog
    When the report renders
    Then the lifetime cell is empty rather than zero
    And no warning is raised

  Scenario: The guardrails still apply
    Given a lifetime total exceeds the sanity bounds
    When the report renders
    Then the existing sanity warning fires for it
    And the column does not silently show an implausible figure
```

- acceptance: the column renders from `core.timelog_totals`; the label makes the
  source unambiguous; empty is distinct from zero; sanity bounds cover it.
- validation: a golden dataset with worklog history spanning outside the report
  window, asserting the lifetime figure and the period figure independently.
- dependencies: none. The code is in place and the gate is met.

### All-source lifetime totals, aggregated from the observed store

- priority: **now** — this is the requirement. The measurement above removes the
  cost objection, so what remains is a display and a source decision, both small.
- problem: the broader ask is total time per project across all sources and all
  time. That is the figure with a real cost, and it has no storage answer.
- non-goals: writing it to `timelog_projects.json`, for the reasons above.
- behavior: a decision, then a slice. The candidates are recomputing from the
  evidence store on demand, or an aggregate maintained alongside it that is
  reconstructible by deletion.
- acceptance: totals are derived from the `observed/` store without invoking a
  collector; no running total is written anywhere; the figure states the window
  it actually covers; and it renders fast enough to feel immediate at roughly 80
  profiles.
- validation: a golden dataset with an observed store spanning outside the report
  window, asserting the lifetime figures and confirming no collector ran. Re-run
  after deleting any derived artifact and confirm identical numbers.
- dependencies: none. The measurement that used to block this is done.

### Give gated decisions an owner

- priority: **later**
- problem: this pass exists because a two-item gate was satisfied and the thing
  it gated stayed off. The same shape appeared twice more this week.
- behavior: when a decision is recorded as gated, the gate's conditions are
  written where they can be checked mechanically, and something reports when they
  are met.
- acceptance: at least the existing gated decisions are expressed as a check that
  fails, or notifies, once its conditions hold.
- dependencies: none, but it is a process change and should not jump work.

---

## Ordering

`now` gains the all-source totals, because that is what was asked for and the
only thing that was blocking it turned out not to exist. It is a display plus a
source decision, both small.

The worklog-only column drops to `later`. It was never the ask, and shipping a
column that is structurally empty for the requester would spend goodwill that is
already scarce.

## Open decisions

1. **What is the figure called?** The withdrawn column's label invited a
   comparison it could not support, and that was the failure. The name is part
   of the fix, so it is a product decision rather than an implementation detail.
2. **Retention.** An all-time figure over a store that prunes is not all-time.
   The figure has to state the window it actually covers.

Settled during review, kept so the reasoning is not lost:

- **Do per-run source flags change a lifetime total?** No. A lifetime total is a
  property of the store, not of the invocation; one that shifts because of a flag
  on today's run is not a lifetime total.
- **Does `--screen-time off` affect it?** The question was badly posed. Screen
  Time contributes no hours at all: its role is `COVERAGE_COMPARATOR`, and
  `collect_presence_comparators` keeps it in a separate daily map that never
  enters the event stream. The flag changes the coverage comparison and its
  evidence-gap warning; no hour figure moves.

## Non-goals for this pass

No code. No new storage. No invoiced totals — that needs billing-log storage and
is its own story.
