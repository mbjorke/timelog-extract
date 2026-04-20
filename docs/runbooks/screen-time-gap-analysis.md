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
- `--out-md PATH` — markdown summary file; default `out/reconciliation/screen_time_gap.md`

The implementation lives in `scripts/calibration/run_screen_time_gap_analysis.py`; `scripts/run_screen_time_gap_analysis.py` is a **stable entrypoint** that forwards there.

## Outputs

- **`screen_time_gap.json`** — full payload: per-day rows, totals, and `project_allocated_gap_hours`.
- **`screen_time_gap.md`** — internal summary with date range, totals, and top gap days.

### Compare two payloads without manual copy/paste

```bash
python3 scripts/compare_screen_time_gap.py --old out/reconciliation/screen_time_gap.old.json --new out/reconciliation/screen_time_gap.json
```

This prints totals delta and day-row delta in one command.

### Day-level Top Sites triage (memory trigger)

```bash
python3 scripts/gap_day_triage.py --day 2026-04-02
```

This reads the selected day from `screen_time_gap.json`, shows top Chrome sites for that day, suggests likely project matches from your profile rules, and prints a ready-to-run `gittan suggest-rules` command.

By default, `gap_day_triage.py` uses `site-first` scoring to prioritize domain anchors over broad term matching.

To force the legacy balanced behavior:

```bash
python3 scripts/gap_day_triage.py --day 2026-04-02 --scoring-mode balanced
```

To explicitly request site-first:

```bash
python3 scripts/gap_day_triage.py --day 2026-04-02 --scoring-mode site-first
```

### Canonical project rollup (recommended)

If multiple repositories/apps are effectively one product line, set a shared `canonical_project` and shared `aliases` so triage suggestions roll up to one business identity.

Example for a single product cluster:

```json
{
  "name": "project-core",
  "canonical_project": "ProductSuite",
  "aliases": [
    "project-core",
    "project-ui",
    "project-cli",
    "Product Suite"
  ]
}
```

## How to read the output (shared interpretation model)

Use these four terms consistently in CLI/app/docs/demo:

- **Estimated hours**: hours reconstructed by Gittan from local traces and session rules.
- **Screen-time hours**: measured reference hours from Screen Time data.
- **Coverage ratio**: `estimated_hours / screen_time_hours`.
- **Unexplained screen-time hours**: measured screen-time not yet explained by current attribution.

### Suggested confidence bands

- **Coverage < 0.70**: low confidence, calibration required.
- **0.70 to 0.85**: usable but should be improved.
- **0.85 to 0.95**: good operational confidence.
- **> 0.95**: excellent (near-complete explanation).

These are operational heuristics for triage, not strict scientific guarantees.

### 3-step day triage loop

1. Pick the top unexplained day from markdown summary.
2. Run `scripts/gap_day_triage.py --day YYYY-MM-DD` to recover context.
3. Apply one focused correction:
   - source/collector availability,
   - project matching terms,
   - session-rule tuning.
4. Re-run analysis and compare payloads with `scripts/compare_screen_time_gap.py`.

Aim to move unexplained hours down and coverage up with one change at a time.

## Tests

Logic is covered by:

- `tests/test_screen_time_gap_analysis.py`
- `tests/test_compare_screen_time_gap.py`
- `tests/test_gap_day_triage.py`

All are included in `./scripts/run_autotests.sh`.

## See also

- **`docs/product/accuracy-plan.md`** — KPIs and golden eval loop.
- **`core/calibration/screen_time_gap.py`** — `analyze_screen_time_gaps(report)`.
