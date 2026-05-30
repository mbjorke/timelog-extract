# Deprecation and Test Weakness Inventory

Status: active guidance  
Last updated: 2026-05-29

## Purpose

Before broad refactors, identify surfaces that are deprecated, compatibility-only,
or unusually expensive to reason about. This keeps new behavior contracts from
accidentally blessing old patterns.

Use this inventory before starting work that touches source collection, review /
triage flows, worklog resolution, truth payloads, or CLI-facing behavior.

## Summary

The repo has a useful regression-heavy test suite and several clear deprecation
markers, but the deprecations and test weak spots are spread across `AGENTS.md`,
runbooks, README copy, code wrappers, and tests.

Refactor order should therefore be:

1. document current behavior and weak spots,
2. write behavior contracts for active surfaces,
3. keep compatibility tests for deprecated surfaces,
4. remove or sunset old surfaces only after active replacements have durable
   tests and docs.

## Deprecated Or Compatibility Surfaces

| Surface | Current replacement | Status | Notes |
| --- | --- | --- | --- |
| `gittan triage-map` | `gittan review` / `gittan review --json` | deprecated alias | Keep behavior stable while the alias exists; do not model new flows after it. |
| `gittan triage`, `triage-domains`, `triage-guided`, `triage-apply` | `gittan review`, `projects-audit`, `projects-trim` | deprecated family | Existing tests may stay as regression guards; new task specs should use canonical commands. |
| `gittan review --uncategorized` / log-cluster review | `gittan review` URL/gap mapping | deprecated path | Avoid extending this path unless there is an explicit migration decision. |
| Repo-local `TIMELOG.md` as primary setup | per-project worklogs under Gittan home, explicit `--worklog`, or configured worklog paths | legacy fallback only | Do not use as the active reporting model for new work. It remains for compatibility and migration from the original visible-in-repo workflow. |
| `rc-*` / `rc/` naming for day-to-day feature work | `task/*` branches and `docs/task-prompts/` | legacy naming | Keep old references when historically accurate; new work should use `task/*`. |
| `docs/legacy/` operational links in code | `docs/runbooks/`, `docs/decisions/`, `docs/specs/`, `docs/product/` | disallowed in user-facing code | Markdown may mention legacy docs as secondary history only. |
| Backward-compatible Python wrappers such as live-terminal and reconciliation wrappers | canonical modules under current packages | compatibility layer | Keep import-smoke coverage; do not add new behavior to wrappers. |

## Weak Test Areas

These are not failures; they are places where a refactor can easily preserve the
wrong thing.

| Area | Current strength | Weakness | Refactor implication |
| --- | --- | --- | --- |
| CLI smoke and regression tests | Good subprocess coverage for real CLI behavior | Many assertions depend on output substrings | Add scenario-level contracts before changing wording or command shape. |
| Triage/review flows | Strong regression history and JSON-shape checks | Deprecated and current flows coexist in the same conceptual space | Separate active behavior contracts from deprecated regression guards. |
| Source collection | Collector registry/status model is clear | Source roles and weights are implicit | Use `docs/specs/source-evidence-policy.md` before adding or reweighting sources. |
| Worklog resolution | Heavily documented in `AGENTS.md` and covered by tests | Legacy fallback and preferred future model can be conflated | State whether a test protects compatibility or target behavior. |
| Timelog health visibility | Global hook setup and worklog paths are documented | Users cannot easily see whether today's capture is healthy | Add health/status contracts before adding more capture paths. |
| Truth payload / invoice truth | Good RFC direction and payload tests | Full evidence/weighting contract is not yet built | Avoid presenting current classified output as approved invoice truth. |
| Doctor/source diagnostics | Useful rows and mode checks | Each source can grow one-off logic | New sources should follow the collector/source contract. |

## Behavior Contract Candidates

Good first candidates for Gherkin-style behavior contracts:

- Worklog path resolution and source strategy.
- Timelog health / capture freshness.
- Source enablement, permissions, and `collector_status`.
- Review / URL mapping canonical command behavior.
- Truth payload split: observed, classified, approved invoice time.
- Source evidence roles and weighting.
- Calendar source behavior before implementation.

## Do Not Build On

Do not use these as templates for new features without an explicit decision:

- Deprecated `gittan triage*` command shape.
- User-facing links to `docs/legacy/`.
- Output-only substring tests as the sole acceptance evidence for a new behavior.
- Compatibility wrapper modules as homes for new logic.
- Treating every source as equal evidence for time, classification, and invoice
  readiness.
- Using repo-local `TIMELOG.md` writes as evidence that the maintained worklog
  pipeline is healthy.

## Recommended Refactor Order

1. Add behavior contracts for current active behavior before moving code.
2. Mark existing tests as either active-contract coverage or compatibility
   regression coverage.
3. Extract shared source/collector patterns only after at least two active
   sources follow the same documented contract.
4. Migrate deprecated command tests last; keep them narrow and focused on
   deprecation warnings plus stable no-surprise behavior.
5. Update this inventory whenever a deprecated surface is removed, extended, or
   promoted back to active status.
