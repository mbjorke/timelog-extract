# Classification Trust Recovery (TDD Playbook)

Status: active recovery plan
Date: 2026-04-23

## Objective

Restore trust in Gittan classification by reducing false attribution and making
classification changes provably safe with repeatable tests.

## Command taxonomy (use consistently)

- **User CLI (`gittan ...`)**: preferred for everyday operational runs and invoicing workflows.
- **Internal scripts (`python3 scripts/...`)**: use for calibration/evaluation pipelines that are not yet exposed as first-class CLI commands.

Rule of thumb: if both exist, use `gittan` as the primary path and keep scripts as explicit internal fallback.

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

## Automation status

Implemented:

- `gittan projects-lint` reports:
  - overlapping `match_terms` across enabled profiles
  - high-risk broad terms
- Use `--strict` to fail fast in local gates/CI.

Example:

- `gittan projects-lint --config timelog_projects.json --strict`

Next:

- tighten duplicate profile cue detection as a dedicated lint code.

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

## Monthly invoice run (locked command)

Primary path (User CLI):

- `gittan report --from 2026-03-01 --to 2026-03-31 --invoice-mode calibrated-a --invoice-ground-truth march_invoice_ground_truth.json`

Internal automation path (scripted batch/check artifact):

- `python3 scripts/calibration/run_month_end_invoice_check.py --ground-truth march_invoice_ground_truth.json --date-from 2026-03-01 --date-to 2026-03-31`

The script writes:

- `out/reconciliation/month_end_invoice_check.json`
- `out/reconciliation/month_end_invoice_check.md`

The script includes a built-in end-date sanity check (`to` vs `to-1 day`) so undercount from wrong end date is visible immediately.

Guidelines:

1. Always set `--to` to the last calendar day in the month.
2. Keep the same `--invoice-ground-truth` file between comparison runs.
3. Treat `--invoice-mode baseline` as analysis mode, not invoice-final mode.
4. Record output JSON and a short delta note in `docs/evals/` for traceability.

