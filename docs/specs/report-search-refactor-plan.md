# Report/Search Refactor Plan

## Goal
Reduce duplicated logic between `gittan report` and `gittan search` while keeping behavior stable.

## Current Problem
- `core/cli_report_status.py` contains near-duplicate timeframe resolution in both commands.
- `TimelogRunOptions` construction is mostly duplicated.
- Minor behavior drift risk increases when one command is updated and the other is not.

## Scope
- Refactor only shared CLI wiring.
- Do not change report aggregation, filtering semantics, or output schema.
- Keep command help text and UX intact except where wording clarifies shared execution path.

## Proposed Design
1. Add `_resolve_timeframe_args(...)` helper in `core/cli_report_status.py`:
   - Inputs: all timeframe flags + optional `date_from`/`date_to`.
   - Behavior: preserve current prompt behavior when no timeframe is provided.
   - Output: normalized `(df_s, dt_s, today, yesterday, last_3_days, last_week, last_14_days, last_month)`.

2. Add `_build_report_options(...)` helper:
   - Builds `TimelogRunOptions` from common fields.
   - Supports command-specific overrides (`all_events=True` for search, etc.).

3. Update `report` and `search` to call both helpers:
   - Keep existing option names and defaults.
   - Preserve existing call path through `run_timelog_cli(options)`.

4. Keep `search` behavior explicit:
   - Continue forcing `all_events=True`.
   - Update docstring wording from “wrapper around report” to “shares report execution path.”

## Test Plan
- Existing suite:
  - `tests/test_cli_search.py`
  - `tests/test_cli_report_additive_summary.py`
  - `tests/test_project_filter_resolution.py`
- Add targeted tests:
  - Verify `report` and `search` resolve identical timeframe flags.
  - Verify `search` still enforces `all_events=True`.
  - Verify prompt path remains unchanged when timeframe is omitted.

## Rollout
1. Implement helper extraction in a dedicated PR.
2. Run `./scripts/run_autotests.sh`.
3. Validate manual smoke commands:
   - `gittan report --today`
   - `gittan search --today --project "time"`
4. Merge only when no output regression is observed.

## Non-Goals
- No changes to collector behavior.
- No changes to calibration logic.
- No changes to rendering in terminal/pdf/json outputs.
