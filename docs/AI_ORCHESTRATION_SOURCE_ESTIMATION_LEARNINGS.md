# Estimating New Data Source Integration (Lovable Desktop)

Date: 2026-04-15

## Why this note exists

We want tighter estimates for "add one new collector" work and fewer review loops.
This note records what happened for Lovable Desktop and turns it into a reusable
estimation model for future sources.

## What was delivered

- Added a new source: `Lovable (desktop)`.
- Wired collector through runtime pipeline + source registry + source ordering.
- Added diagnostics row in `gittan doctor`.
- Added tests for source discovery/parsing helpers.
- Added fallback strategy:
  - Prefer Chromium `History` DB when present.
  - Fall back to app storage signal files (Local/Session/IndexedDB) when `History` is absent.

## Effort breakdown (observed)

This integration behaved like a medium-complex source due to unknown storage shape.

- Phase 1: discovery + assumptions check (paths, files, viability) -> ~20-30 min
- Phase 2: baseline collector + wiring (registry/runtime/pipeline/sources) -> ~25-40 min
- Phase 3: diagnostics + tests + changelog -> ~15-25 min
- Phase 4: reality check on user machine + fallback redesign -> ~20-40 min

Observed total: ~80-135 min (including one redesign pass after real-world validation).

## Key lessons for estimate accuracy

1. "Storage certainty" dominates estimate quality.
  - If source data format/path is known and stable, implementation is much faster.
  - If storage is unknown (or app is new), add explicit discovery buffer.
2. "First machine validation" is mandatory before final estimate lock.
  - Unit tests can pass while the real app stores data differently.
3. Plan for fallback from day one.
  - Desktop apps often differ across installs/profiles.
  - Build for "primary path + fallback path" if scope allows.

## Reusable estimate model (for future collectors)

Use this quick sizing rubric before coding:

- `S1 Known SQLite/log source + existing parser pattern` -> 30-60 min
- `S2 Known source + partial new parsing logic` -> 60-120 min
- `S3 Unknown/unstable source + fallback needed` -> 120-240 min

Then apply multipliers:

- +25% if diagnostics (`doctor`) updates are required
- +20% if new source should appear in source analytics/status ordering
- +30-60 min for first real-user validation session

## Practical orchestration loop (to improve AI estimates)

For each new source, run these checkpoints explicitly:

1. `Discover` (10-20 min cap): identify concrete files + sample records.
2. `Implement thin` (20-40 min): collector + minimal wiring only.
3. `Validate live` (10-20 min): run on the target machine immediately.
4. `Harden` (20-40 min): fallback, doctor row, tests, changelog.
5. `Re-estimate` after checkpoint 3 (not before).

This keeps estimates adaptive and avoids false confidence from synthetic-only tests.

## Definition of done for new source RC

- Collector status appears in JSON payload (`collector_status`).
- Source appears in `--source-summary` when data exists.
- `gittan doctor` shows clear status/reason for missing prerequisites.
- At least one dedicated test file for source-specific helper logic.
- Changelog entry under `Unreleased`.