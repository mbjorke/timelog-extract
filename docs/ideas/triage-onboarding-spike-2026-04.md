# Spike: faster triage onboarding (top-sites + timestamp)

Date: 2026-04-21

## Why this spike

We want the fastest path from "install + first run" to "useful project mapping"
without making users hand-edit `timelog_projects.json`.

This spike focuses on two goals:

1. Faster onboarding value (first successful mappings in minutes).
2. Better confidence per mapping by adding timing context ("which top site belonged
   to which project around this timestamp?").

## Context from existing docs (comparison)

This spike builds on documented ideas, not a brand-new direction:

- `docs/runbooks/gittan-triage-agents.md`
  - Today: `gittan triage --json` provides day-level gaps, `top_sites`,
    suggestions, and automation hints.
  - Gap: no explicit "site + timestamp -> likely project" UX loop for quick
    onboarding decisions.
- `docs/sources/ai-assisted-config.md`
  - Vision: reduce config authoring friction and guide users into valid project
    structure.
  - Gap: concrete short-loop UX for first-day onboarding is still thin.
- `docs/runbooks/cli-polish-backlog-for-apr29.md`
  - Current bias: fast, low-risk polish and clear next actions.
  - Relevance: this spike should keep the same "small increments, measurable
    value" principle.

## Hypothesis

If we show top sites with lightweight timestamp anchors and a one-click
"map to project" flow, users will complete first useful onboarding faster and
reduce uncategorized hours sooner.

## Proposed spike scope (small, measurable)

### S1 — Timestamp-enriched triage payload

Status: built and covered by `tests/test_cli_triage.py`.

Add optional timestamp hints in triage JSON per top site/day, for example:

- first_seen time
- last_seen time
- one representative session timestamp window

Constraints:

- Keep page titles out (privacy).
- Keep payload compact; domains + counts remain primary.

### S2 — Quick onboarding mode (project-first mapping)

A minimal "quick onboarding" path:

1. Show top 3 unexplained days.
2. For each day, show top sites + timestamps + top 2 project suggestions.
3. Apply 1-2 domain mappings per day.
4. Confirm via dry-run before write.

### S3 — Compare against existing path

Run a side-by-side comparison:

- baseline: current triage flow
- spike: timestamp-enriched quick path

Measure:

- time to first applied mapping
- mappings accepted per minute
- uncategorized delta after one session

## Fast value iteration plan

1. Implement only payload/tiny UX needed for S1 + S2.
2. Validate on real local data (no broad refactor).
3. Document wins/losses in this file.
4. Promote to `docs/specs/` only if metrics improve.

Current next step: validate S2 as a beta-onboarding path. The question is not
whether the engine can run; it is whether a new user can reach a useful project
config quickly with evidence, suggestions, and explicit approval before writes.

## Open questions

- Should timestamp hints be strict session bounds or coarse buckets (e.g. 09:00-11:00)?
- Is one representative timestamp enough, or do we need first+last per domain?
- Should onboarding default to site-first always, or allow quick switch to balanced?

## Non-goals in this spike

- Full UI redesign.
- New remote backend requirements.
- Any change that weakens current read-only contract of `triage --json`.

## Exit criteria

The spike is successful if at least one of these is true:

- onboarding loop is clearly faster in practice (time-to-first-apply down), or
- mapping confidence is clearly higher (fewer immediate corrections), or
- we produce enough evidence to reject timestamp UX quickly and avoid overbuilding.
