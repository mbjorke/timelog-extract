# Timelog Truth Check Runbook

Status: active workflow

## Purpose

Run a deterministic replay check for `gittan report` and emit standard artifacts
for review and CI evidence.

## Preconditions

- Run from repo root.
- Use a **closed time window** by default (`--to` should not be today).
- Use `--allow-open-window` only for exploratory checks, never as deterministic
  compliance evidence.

## Command

```bash
bash scripts/timelog_truth_check.sh --from 2026-01-01 --to 2026-01-31 --out-dir out/timelog_truth_check/manual
```

Optional flags:

- `--projects-config <path>`: use alternate project config.
- `--allow-open-window`: bypass closed-window guard (exploratory only).

## Expected artifacts

The output directory MUST contain:

- `benchmark_manifest.json`
- `benchmark_metrics.json`
- `determinism_replay_report.json`
- `README.md`

## Reviewer checklist

- `determinism_replay_report.json` shows `normalized_equal=true`.
- `benchmark_metrics.json` has `gate_decision` visible (`GO` / `conditional GO` /
  `NO-GO`).
- `README.md` summarizes the run window and how to read each artifact.

## Validation evidence anchors

- Script contract tests: `tests/test_timelog_truth_check_script.py`
- Script under test: `scripts/timelog_truth_check.sh`
- RFC policy source: `docs/specs/timelog-truth-standard-rfc.md`

## Troubleshooting

- Guard error about open window:
  - Move `--to` to yesterday (or earlier), then rerun.
- Hash mismatch / drift keys present:
  - Treat as determinism failure for the tested window.
  - Inspect drift keys in `determinism_replay_report.json`.
  - Re-run with identical inputs after fixing root cause.
