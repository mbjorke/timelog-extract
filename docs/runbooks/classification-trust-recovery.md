# Classification Trust Recovery (TDD Playbook)

Status: active recovery plan
Date: 2026-04-23

## Objective

Restore trust in Gittan classification by reducing false attribution and making
classification changes provably safe with repeatable tests.

## Immediate stabilizers (done first)

1. Remove broad/ambiguous `match_terms` from sensitive customer profiles.
2. Disable duplicate/legacy profiles that overlap active customer projects.
3. Re-run a known day (`--yesterday`) and inspect session rows before billing use.

## Guardrail workflow (for every config or classifier change)

1. **Reproduce**: capture one problematic day and expected outcome.
2. **Test first**: add/extend a failing unit test or fixture scenario.
3. **Fix**: minimal code/config change to make the test pass.
4. **Regression**: run full autotests + CLI smoke.
5. **Document**: add why the fix exists and what it protects against.

## TDD test categories (must keep growing)

### A) Classifier behavior (`core/domain.py`)

- Exact-vs-generic term priority.
- Tie-break determinism and explicit rules for equal score.
- Profile overlap cases (same term in multiple profiles).

### B) Aggregation/report integrity (`core/report_aggregate.py`, status/report UX)

- Detect when project rows are non-additive against total.
- Ensure UI labels clearly explain overlap when it exists.
- Add a test that fails if totals are presented as additive when they are not.

### C) Config health checks

- Fail or warn when enabled profiles share high-risk terms.
- Warn on generic terms (`koden`, `formulär`, etc.) in customer projects.
- Warn on duplicate active profiles for same repository context.

## New automation target (next iteration)

Add a lightweight command/check:

- `gittan projects --lint` (or equivalent internal helper) that reports:
  - overlapping `match_terms` across enabled profiles
  - broad risky terms
  - duplicate profile cues

Gate this in CI/autotests so risky config drift is caught before merge.

## Acceptance criteria (trust bar)

We treat the system as recovered for day-to-day use when:

1. The known problematic day classifies as expected in fixture tests.
2. Overlap lint warnings are present and actionable.
3. Status/report presentation no longer implies false additive totals.
4. Full autotests stay green across these scenarios.

## Operational rule until full recovery

For invoice-critical days, always run:

- `gittan report --<timeframe> --source-summary`
- inspect top sessions + project mapping manually

Do not rely on `status` table totals alone for billing until integrity tests and
UI clarifications are merged.
