# Agent Inline CLI UX Validation

Status: Active routine  
Cadence: During active feature development  
Owner: Active agent

## Purpose

Reduce late surprises by validating CLI behavior and wording while changes are still
small. The agent should run `gittan` commands inline during implementation, not only
at PR-final test time.

## Decision

For CLI-impacting work, the agent must execute a minimal inline smoke loop after
meaningful edits and before claiming the change is done.

## Default inline smoke loop

1. **Version/runtime sanity**
   - `python3 -m timelog_extract -V`
2. **Core report UX sanity**
   - `python3 -m timelog_extract report --today --source-summary`
3. **Feature-targeted command(s)**
   - Run the command path touched by the change.
   - Example for suggestions flow:
     - `python3 -m timelog_extract suggest-rules --project "Time Log Genius" --today`
4. **Result note in agent output**
   - Report expected vs actual behavior in 1-3 lines.
   - If blocked, report exact blocker and stop guessing.

## One-command bundle (repo root)

Agents can run the same loop mechanically:

```bash
bash scripts/cli_impact_smoke.sh
```

Override entrypoint if needed: `TIMOLOG_ENTRY=timelog_extract.py PYTHON=python3.12 bash scripts/cli_impact_smoke.sh`.

## CI experiment loop (A/B/C setup quality)

For setup/rule-suggestion improvements, CI also runs deterministic fixture experiments:

- `bash scripts/run_cli_experiments_ci.sh`
- produces JSON + markdown scorecards in `out/cli-experiments/`
- evaluates variants `A/B/C` on:
  - event classification rate
  - recategorized hours
  - setup speed
  - suggestion acceptance ratio

Default mode is report-only (`STRICT_CLI_EXPERIMENTS=0`).
Strict gating is enabled with `STRICT_CLI_EXPERIMENTS=1`.

## Variant promotion policy

Until evidence is stable, default behavior remains unchanged.
Promotion to a new default variant requires:

1. candidate variant passes all thresholds in CI strict mode
2. pass result holds for at least two consecutive runs
3. promotion decision is recorded in `CHANGELOG.md` with scorecard evidence path

If a promoted default regresses, fall back to previous default and continue in report-only mode.

## March reconciliation loop (real-data calibration)

When billed truth is available, run reconciliation on the same month range:

- `python3 scripts/run_march_reconciliation.py --ground-truth <path-to-json>`
- compares baseline + A/B/C projection against invoiced hours per project
- writes:
  - `out/reconciliation/march_scorecard.json`
  - `out/reconciliation/march_scorecard.md`

Ground truth format:

```json
{
  "projects": {
    "Project A": 12.5,
    "Project B": 8.0
  }
}
```

## Screen Time gap loop (coverage calibration)

Run this analysis to understand where estimated project time diverges from system activity:

- `python3 scripts/run_screen_time_gap_analysis.py`
- outputs:
  - `out/reconciliation/screen_time_gap.json`
  - `out/reconciliation/screen_time_gap.md`

Reported metrics:

- day-level coverage ratio (`estimated_hours / screen_time_hours`)
- unexplained screen time (`screen - estimated`, floor at 0)
- over-attributed time (`estimated - screen`, floor at 0)
- project-allocated signed gap (day gap distributed by project share)

## Unified March calibration report

For a single decision-ready run (invoice + screen-time in one artifact):

- `python3 scripts/run_march_calibration_report.py --ground-truth <path-to-json>`
- outputs:
  - `out/reconciliation/march_calibration.json`
  - `out/reconciliation/march_calibration.md`

## Guardrails

- Prefer non-destructive commands in routine smoke checks.
- If write paths are involved, use explicit confirmation and existing backup behavior.
- Do not mutate or move `timelog_projects.json` as part of test setup.
- Keep checks fast; use the smallest command set that validates changed UX.

## Exit criteria for "done"

Work is not considered done until:

- inline smoke loop has run for the changed CLI path,
- CI fixture experiment has run when A/B/C behavior or setup heuristics changed,
- observed UX is reported,
- and blocking mismatches are either fixed or explicitly escalated.
