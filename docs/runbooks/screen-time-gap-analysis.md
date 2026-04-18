# Screen Time gap analysis (estimates vs measured screen time)

Use this when you want **structured reconciliation** between:

- **Estimated hours** from Gittan’s merged activity, and  
- **Screen Time** totals (when Screen Time collection is enabled for the run).

Day-level metrics include coverage, unexplained screen time, and over-attributed estimate hours. Project-level **signed gap** allocation is included in the JSON payload for calibration workflows.

## Prerequisites

- **Screen Time** available to the engine for the date range (macOS permission; see collector docs and `gittan doctor`).
- Valid **`timelog_projects.json`** and usual report inputs for the range you analyze.

## Run

From the repository root (or any cwd if you pass `--projects-config`):

```bash
python3 scripts/run_screen_time_gap_analysis.py
```

Optional arguments:

- `--projects-config PATH` — default `timelog_projects.json`
- `--date-from YYYY-MM-DD` / `--date-to YYYY-MM-DD` — if omitted, defaults to **last calendar month** (first day through last day).
- `--out-json PATH` — default `out/reconciliation/screen_time_gap.json`
- `--out-md PATH` — short pointer file; default `out/reconciliation/screen_time_gap.md`

The implementation lives in `scripts/calibration/run_screen_time_gap_analysis.py`; `scripts/run_screen_time_gap_analysis.py` is a **stable entrypoint** that forwards there.

## Outputs

- **`screen_time_gap.json`** — full payload: per-day rows, totals, and `project_allocated_gap_hours`.
- **`screen_time_gap.md`** — minimal pointer; details are in JSON.

## Tests

Logic is covered by `tests/test_screen_time_gap_analysis.py` (part of `./scripts/run_autotests.sh`).

## See also

- **`docs/product/accuracy-plan.md`** — KPIs and golden eval loop.
- **`core/calibration/screen_time_gap.py`** — `analyze_screen_time_gaps(report)`.
