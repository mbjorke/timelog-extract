# Worklog-first strategy plan

## Goal

Make reports more predictable and useful for repo-centric workflows by treating `TIMELOG.md` (or explicit `--worklog`) as the primary timeline when available, while keeping other collectors as supporting evidence.

## Why this change

- Scenario A in `docs/MANUAL_TEST_MATRIX_0_2_x.md` can look "empty" even when sources are accessible, because classification/filtering depends on fallback profile keywords.
- Repo users often already maintain meaningful log entries (commits, tickets, notes) in `TIMELOG.md`.
- A worklog-first approach improves trust: "what I wrote in my worklog is the base truth; other sources enrich it."

## Operator precondition (important)

For worklog-first to deliver consistent value across repositories, users should have machine-level timelog capture enabled via global git hooks.

- Canonical setup guide: `GLOBAL_TIMELOG_AUTOMATION.md`.
- Required global git settings:
  - `core.hooksPath` pointing to a global hooks directory (for example `~/.githooks`)
  - `core.excludesFile` including `TIMELOG.md` to prevent accidental commits
- Expected outcome: each commit appends a timestamped entry in repo-local `TIMELOG.md`, giving worklog-first a stable baseline timeline.

This is a recommended precondition for testing and rollout; worklog-first must still degrade gracefully when this setup is missing.

## Product behavior (target)

### Primary timeline source

- If `--worklog PATH` is set and readable, use it as primary.
- Else if repo-root `TIMELOG.md` exists and is readable, use it as primary.
- Else fall back to current multi-source behavior (no hard failure).

### Source roles

- **Primary (worklog):** defines baseline events/time windows for report totals.
- **Supporting (Chrome, Mail, Screen Time, GitHub, Cursor, etc.):** add context, evidence, and detail around primary windows.
- When supporting data conflicts with worklog windows, worklog wins by default.

### Reporting transparency

- Terminal and JSON should make role assignment explicit (`primary_source`, `supporting_sources`).
- If no worklog is found, emit a clear note that report is running in fallback mode.

## CLI and configuration proposal

### New strategy control

- Add `--source-strategy` with values:
  - `auto` (default): use worklog-first when worklog exists; otherwise fallback behavior.
  - `worklog-first`: require worklog as primary if found; if missing, warn and fallback (non-breaking).
  - `balanced`: current behavior (all enabled sources treated similarly).

### Config support

- Add optional config key: `"source_strategy": "auto|worklog-first|balanced"`.
- CLI flag overrides config.

### Optional strict mode (later)

- Future flag: `--require-worklog` to fail early when user explicitly wants worklog-first but no worklog is available.

## Implementation plan (phased)

## Phase 1 - Runtime semantics (minimal risk)

- Add strategy resolution in runtime options/composition.
- Mark one source as primary when strategy resolves to worklog-first and worklog is available.
- Keep existing collectors and parsing intact.
- Ensure no regression for users without worklog.

## Phase 2 - Aggregation and conflict policy

- In aggregation/session-building, prioritize worklog-derived windows for totals.
- Attach supporting evidence without double-counting overlapping intervals.
- Preserve `--include-uncategorized` behavior, but do not hide primary worklog events by default.

## Phase 3 - Output contracts

- Add strategy/source role metadata to truth payload (`schema` compatible extension).
- Update terminal source summary to show primary/supporting split.
- Document behavior in `README.md` and `docs/SOURCES_AND_FLAGS.md`.

## Phase 4 - Validation and rollout

- Extend deterministic checks and manual matrix scenarios:
  - New deterministic assertion: non-empty worklog with worklog-first yields stable `totals.event_count`.
  - Scenario A/B comparison with and without worklog-first.
- Ship behind default `auto` to minimize migration risk.

## Acceptance criteria

- With readable worklog and `--source-strategy auto`, reports no longer appear unexpectedly empty for normal date ranges where worklog has entries.
- With no worklog, behavior remains equivalent to current baseline (no crash, clear status note).
- JSON payload includes versioned metadata describing selected strategy and source roles.
- Existing tests pass; new strategy tests cover:
  - worklog present + auto
  - worklog missing + auto
  - balanced parity
  - include-uncategorized interaction

## Risks and mitigations

- **Risk:** over-weighting noisy/low-quality worklog entries.
  - **Mitigation:** keep supporting evidence visible and expose strategy in output.
- **Risk:** behavior surprise for users expecting current balanced model.
  - **Mitigation:** `balanced` mode remains available; document default `auto` clearly.
- **Risk:** aggregation complexity and double-counting.
  - **Mitigation:** add overlap tests and deterministic fixtures before rollout.

## Open questions

- Should `worklog-first` become the hard default in a future minor release, or remain `auto` indefinitely?
- Should primary worklog entries always be included even when uncategorized, or stay behind `--include-uncategorized`?
- Do we want a separate "evidence confidence" score per session/event for supporting signals?

## Suggested first PR scope

- Add `--source-strategy` + runtime resolution (`auto`, `worklog-first`, `balanced`).
- Add output note in terminal summary for selected strategy.
- Add unit tests for strategy resolution and no-regression fallback behavior.
- Keep aggregation rules mostly unchanged in first PR to reduce risk; follow with phase 2 PR.
