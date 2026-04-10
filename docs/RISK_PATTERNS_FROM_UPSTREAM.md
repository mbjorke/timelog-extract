# Upstream Risk Patterns (ActivityWatch + gtimelog)

This note maps Timelog Extract v1 risks to concrete patterns observed in upstream projects and recommends whether to adopt, adapt, or reject each pattern.

## Inputs used

- `docs/V1_SCOPE.md`
- `docs/PRIVACY_SECURITY.md`
- `docs/ACCURACY_PLAN.md`
- ActivityWatch README (`ActivityWatch/activitywatch`)
- ActivityWatch core README (`ActivityWatch/aw-core`)
- gtimelog format spec (`gtimelog/gtimelog`, `docs/formats.rst`)

## Risk-to-pattern decisions

| Risk | Upstream pattern | Decision | Action for Timelog Extract |
|---|---|---|---|
| Misclassification from noisy multi-source data | ActivityWatch separates raw event capture from query/transform layers (`aw_datastore`, `aw_transform`, `aw_query`) and keeps raw data queryable. | **Adapt** | Keep collectors "dumb" and bias intelligence to report/query stage. Avoid irreversible transforms during collection. Preserve source-specific detail in event payloads where possible. |
| Source fragility (schema/path/log changes) | ActivityWatch uses watcher-level boundaries (one source per component) so failures isolate cleanly. | **Adopt** | Continue strict per-source collector boundaries in `collectors/*` + status reporting in `core/collector_registry.py` and `core/pipeline.py`. Add small source-specific regression tests when parsers change. |
| Privacy/consent regressions | ActivityWatch's core positioning: local data ownership and optional collection scope. | **Adopt** | Keep first-run consent and per-source toggles as non-negotiable (`docs/PRIVACY_SECURITY.md`). Treat new sources as opt-in by default until explicit product decision says otherwise. |
| Billing defensibility / auditability | gtimelog uses strict append-only `timelog.txt` grammar with explicit timestamps and simple comments; low ambiguity. | **Adapt** | Keep dual-format worklog support (`md` + `gtimelog`) but preserve explicit timestamp semantics. Prefer deterministic parsing and transparent fallbacks over "smart" guesses. |
| Silent parser ambiguity | gtimelog format defines clear line grammar and comment behavior; unsupported lines are effectively non-entries. | **Adopt** | Keep explicit `--worklog-format {auto,md,gtimelog}` and deterministic auto-detection. If format is forced and parse yield is unexpectedly empty, emit a clear warning in collector status. |
| Over-promising precision to users | ActivityWatch exposes raw events and query tooling, making uncertainty inspectable. | **Adapt** | Lean on truth payload + source summaries (`--format json`, `--source-summary`) for inspectability. Add confidence/ambiguity indicators in future UX rather than presenting single-number certainty. |
| Scope creep into "everything tracker" | gtimelog remains intentionally narrow; ActivityWatch's breadth increases operational complexity. | **Adopt** | Keep v1 source scope constrained to `docs/V1_SCOPE.md`. Gate any additional source behind explicit ROI and accuracy impact, not "possible to collect". |
| Time semantics edge cases (timezone/day boundaries) | gtimelog explicitly documents timezone limitations and virtual-midnight caveats. | **Adapt** | Document known boundary behavior for worklog formats and add focused tests around local timezone and day transitions before broadening formats further. |

## Immediate next actions (low effort, high risk reduction)

1. Add a collector-status warning when `--worklog-format` is forced and parse result is zero entries.
2. Add one regression test each for:
   - gtimelog comment + malformed line tolerance
   - timezone/day boundary parsing for worklog entries
3. In report output, make source-level evidence easy to inspect when attribution is weak (aligns with `docs/ACCURACY_PLAN.md` Iteration 2).

## Decision summary

- **Adopt now**: source isolation, local-first consent defaults, deterministic parsing.
- **Adapt now**: raw-vs-derived separation and explainable uncertainty in reports.
- **Reject for v1**: broad ActivityWatch-like expansion in source surface area before accuracy targets are stable.
