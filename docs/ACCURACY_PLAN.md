# Accuracy Plan

This plan defines how to measure and improve timereporting accuracy for dev/ops workflows.

## Primary Goal

Be the most accurate local-first timereporting tool for technical work.

## KPIs

- Attribution accuracy: `>= 85%`
- Uncategorized rate: `<= 15%`
- Session hour delta vs manual baseline: `<= 20%`
- Correction time: `< 3 min/day`
- Time Report Export readiness: `< 60 sec`

## Iteration 1: Baseline Measurement

### Deliverables

- Golden dataset JSON file under `tests/fixtures/golden_dataset.json`
- Eval script output at `docs/evals/latest.md`
- Baseline KPI snapshot committed in docs

**How to run:** `python3 scripts/run_golden_eval.py --check` (sets `TZ=UTC` before loading the engine; compares `golden_dataset.json` expectations to `run_timelog_report`). Refresh expected hours after intentional pipeline changes: `python3 scripts/run_golden_eval.py --print-expectations`. Covered by `tests/test_golden_eval.py` (invoked from `scripts/run_autotests.sh`).

### Dataset shape

For each expected item:

- `date`: `YYYY-MM-DD`
- `project`: expected project name
- `hours`: expected hours for that date/project

## Iteration 2: Classification Quality

### Focus

- better ranking of terms (repo/path terms above generic browser terms)
- reduce silent misclassification
- improve confidence handling for ambiguous events

### Success criteria

- measurable lift in attribution accuracy
- no regression in correction time

## Iteration 3: Correction Loop

### Focus

- local overrides for repeated edge cases
- high-impact correction suggestions in report

### Success criteria

- correction time below target
- stable weekly accuracy trend

## Weekly Review

- Run eval on golden dataset
- Review top mismatch rows
- Implement one targeted rule improvement
- Re-run eval and log KPI delta
