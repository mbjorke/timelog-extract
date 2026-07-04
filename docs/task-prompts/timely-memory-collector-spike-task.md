# Task Prompt: Timely Memory local buffer — presence collector spike

## Traceability

- story_id: GH-285
- spec_status: draft
- implementation_status: not built
- created_at: 2026-07-03
- last_updated_at: 2026-07-03
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-07-03: Initial draft from Memory.app local-artifact analysis.
  - 2026-07-04: Slice 2 built — scripts/run_timely_memory_benchmark_export.py (runbook Step 2 automation: spans + per-hour presence TSVs, private/-only output guard, read-only access). Live-validated on 2026-07-03: 35310 samples -> 1244 spans, 9.81h presence. (Slice 1 status tracked on the #290 branch.)

## Problem

Gittan infers session duration from event density, which under-covers passive
spans (reading, browsing without structured logs) — the known gap class behind
GH-164 (#258). Timely's Memory desktop app keeps a **local SQLite buffer** of
foreground samples (~1 entry/second: app name, window title, browser URL) that
persists on disk after cloud upload. Read locally and read-only, it is a
high-resolution presence/duration signal Gittan can consume without any API,
account, or network dependency — and it automates Step 2 of
`docs/runbooks/timely-gittan-event-ledger-benchmark.md` (today a manual export).

Scope note: this is a **spike** — validate value and contract before promising a
Tier A source. Time-box matters: the evaluation window (active trial with Memory
running) ends mid-July 2026.

## User value

- Continuous foreground durations close the passive-gap misses observed in the
  2026-07-02 benchmark (uncovered spans between structured events).
- Ledger benchmark becomes reproducible/scripted instead of screenshot-driven.
- Pattern generalizes: ActivityWatch (open source) exposes the same shape for
  users without Timely (see backlog below).

## Non-goals

- No writes to the third-party database, ever (read-only; copy or immutable
  open; never touch WAL ownership).
- No dependency on the Timely API/cloud/account.
- No shipping as default-on: strictly opt-in.
- Not a general "screen recording" feature — foreground titles only, from a
  buffer the user's own app already maintains.
- Exact third-party schema/paths stay out of public docs (see decision below).

## Behavior (target)

```gherkin
Feature: Timely Memory local buffer as an opt-in presence source
  A locally persisted foreground-sample buffer provides presence and duration
  context without leaving the machine.

  Scenario: Opt-in only
    Given the Timely Memory buffer exists on disk
    And the user has not enabled the source
    When a report runs
    Then no Memory data is read
    And doctor lists the source as available but disabled with a reason

  Scenario: Read-only access
    Given the source is enabled
    When the collector runs
    Then the third-party database file is opened read-only (or from a copy)
    And the original file's bytes and mtime are unchanged after collection

  Scenario: Presence role, not work truth
    Given Memory samples cover a span with no direct work evidence
    When the report is generated
    Then the span contributes presence/duration context (coverage_comparator role)
    And it does not by itself create classified project time
    And it never promotes time toward billable

  Scenario: Source disappears gracefully
    Given the user uninstalls the Memory app or the buffer is purged
    When a report runs
    Then the collector reports "unavailable" via collector_status
    And the report completes normally without the source
```

## Slices

### Slice 1 — spike: read + evaluate (priority: now, time-boxed ≤ trial window)

- Read the local buffer read-only; map samples to Gittan's presence layer with
  evidence role `coverage_comparator` (same class as Screen Time — see
  `docs/specs/source-evidence-policy.md`).
- Registered via `core/collector_registry.py` with `enabled` off by default,
  doctor visibility, and a synthetic-DB fixture test (never a real capture in
  the repo).
- Deliverable: spike findings — duration-gap lift on 2–3 benchmark days
  (recorded in `private/benchmarks/`), plus GO/NO-GO on promoting the source.
- acceptance: the four scenarios above pass with a synthetic fixture DB.
- validation: fixture tests + one real-day gap comparison vs Screen Time.

### Slice 2 — benchmark runbook automation (priority: now, small)

- Script the ledger-benchmark Step 2 export from the local buffer (replaces
  manual UI copying); output lands in `private/benchmarks/` only.
- Public runbook text refers to "the tracker's local buffer, if present"
  generically.

### Backlog entry — ActivityWatch source (priority: later)

- Same contract (opt-in, read-only local DB, `coverage_comparator`) for
  [ActivityWatch](https://activitywatch.net/) users without Timely; existing
  idea doc: `docs/sources/activitywatch-integration.md`. Promote to its own
  task-prompt only after the spike's GO.

## Dependencies / open decisions

- **Public-docs boundary (decide before merge of slice 2):** proposal — public
  spec/runbook name the capability ("local foreground-sample buffer") but keep
  exact third-party paths, table names, and schema in `private/benchmarks/`
  notes. Rationale: interop analysis on one's own machine is legitimate, but
  publishing a competitor's internal schema in-repo invites friction ahead of a
  partner conversation.
- Retention: their app controls purging; if the spike shows value, durability
  belongs to the shadow log (GH-151 / config-default spec), not to re-reading
  their buffer.
- Consent copy: follow the calendar-source opt-in pattern (explicit flag +
  config), wording per `docs/sources/sources-and-flags.md`.
- Relates: GH-164 (#258 passive web duration), GH-146 (presence band),
  companion spec `attended-agent-time-task.md` (sharper attendance classifier).
