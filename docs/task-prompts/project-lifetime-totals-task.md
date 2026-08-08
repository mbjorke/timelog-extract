# Total time per project: the gate is already met, and the storage is not config

A product-owner pass on bringing back per-project lifetime totals. It corrects
two premises, finds the blocking gate satisfied, and separates the withdrawn
column from the larger feature it is usually confused with.

No code in this pass.

## Traceability

- story_id: `GH-537`
- superseded_item: `GH-536` (closed, not built — see the backlog section)
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
  - benchmark of classification + session math at 82 profiles, and of
    `collect_git_commit_timestamps` over one repository's full history
  - **not covered:** the lifetime rendering path itself. `timelog_totals` is
    still `{}` at the stub and no lifetime column exists, so nothing here
    verifies output. That is `GH-537`'s acceptance to satisfy, not this pass's.
- validation.decision: GO **for the planning claims only** — the gate check, the
  cost measurements, and the priority ordering. It asserts nothing about an
  implementation that does not exist yet.
- changelog:
  - 2026-08-08: Review pass. Split the combined `story_id` (the live story is
    GH-537 now that GH-536 is closed), scoped `validation.decision` to the
    planning claims since nothing here verifies an unbuilt rendering path,
    changed the lifetime span from "all time" to the retained observation
    window, and made the worklog column's priority agree with its label
    (`priority:do-not-build`, corrected on the issue too).
  - 2026-08-08: Third correction. The speed complaint was about the *Git-only*
    column, not the withdrawn one: one `git log` over all history per profile,
    about 6.7s at 82 profiles, dormant only because `git_repo` is unset.
    Recorded here and on #524, which would activate it.
  - 2026-08-08: Second correction. Reframed the store as durability rather than
    performance (logs rotate; the answer must survive), withdrew the
    `--screen-time off` question as mis-posed since Screen Time contributes no
    hours, and closed #536 once the TIMELOG retirement in #408 made it a surface
    on replaced storage.
  - 2026-08-08: Corrected after learning the requester's setup — 82 profiles and
    no worklog. Swapped the priorities: the worklog-only column cannot serve him
    and is closed; all-source totals become the `now` item. Measured the
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
worth caching.

**And speed was never the real reason to read from the store.** Source logs
rotate and disappear; the shadow-log spec exists because evidence for work that
genuinely happened is otherwise lost. A slow all-time query is acceptable — nobody
asks for a year of history often. Finding the answer *gone* because an IDE pruned
its logs is not. Aggregating from `observed/` is therefore correct even if
recomputation were free, and the measurement merely removes the last thing left
to argue about. It also sets the feature's honest ceiling: the figure covers what
the store retained, which is why it must state its window instead of claiming
all-time.

**The Git-only column, by contrast, really is slow**, and that is the one the
speed complaint was about. `core/git_totals.py::compute_git_project_totals` runs
one `git log` subprocess per profile with a `git_repo`, over all history —
`dt_from`/`dt_to` default to 1970–2099 — and `git_repo` accepts a list, so the
invocation count can exceed the profile count.

| | |
| --- | --- |
| One repository, full history | 533 commits in **0.081s** |
| × 82 profiles, serial | **~6.7s** |

Two unrelated costs, then, and only one of them was ever measured. Aggregation
scales with **events** and is cheap. The `--git` column scales with **profile
count** and is serial subprocess work. It is dormant today only because no
profile has `git_repo` set, which means #524 — the issue that wires it up —
activates it. Flagged there; the fixes are ordinary when someone wants them,
since the loop is embarrassingly parallel and re-reads immutable history on every
run.

## What is actually two different features

The withdrawn column and "total time for a project" are usually spoken of as one
thing. They are not, and conflating them is why the ask keeps stalling.

| | Withdrawn column (#536) | Lifetime totals (#537) |
| --- | --- | --- |
| Sources | worklog only (`TIMELOG.md`) | all sources |
| Span | all time in principle, in practice whatever the worklog holds | the retained observation window |
| Cost | cheap — one file parse | cheap — measured above |
| State | **closed, not built** — blank for the requester, and its storage is being retired by #408 | the live requirement |

Neither is blocked by cost. The first is closed because it cannot answer the ask
on the installation that made it; the second is unblocked because the storage
question turned out to have no cache in it. "The retained observation window" is
deliberate: an all-time claim over a store that prunes would be false, which is
why the figure has to state what it covers.

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

The worklog-only column is **not being built**: #536 is closed, and its label is
`priority:do-not-build`. It was never the ask, shipping a column that is
structurally empty for the requester would spend goodwill that is already scarce,
and #408 is retiring the storage it reads.

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
