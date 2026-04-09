# Timelog Extract

Timelog Extract aggregates local activity signals into project/customer time reports and optional invoice PDFs.

## Current Deliverables

- Refactored CLI core in `timelog_extract.py` with cleaner orchestration.
- Phase 0 friend-trial runner: `scripts/friend_trial.py`.
- GUI-first Cursor extension scaffold in `cursor-extension/`.
- Productization docs in `docs/`:
  - `AGENTIC_EVALUATION.md`
  - `V1_SCOPE.md`
  - `PRIVACY_SECURITY.md`
  - `SIMILAR_REPOS_CHECKLIST.md`

## Quick Start (Friend Trial)

1. Create/activate Python 3.9+ environment.
2. Install dependencies:
  - `python3 -m pip install -e .`
3. Run:
  - `python3 scripts/friend_trial.py --today --invoice-pdf`
4. Share feedback in `friend_trial/FEEDBACK_TEMPLATE.md`.

## CLI Usage

- Today:
  - `python3 timelog_extract.py --today --source-summary --invoice-pdf`
- Same with a plain-English executive blurb after the tables (rule-based, offline):
  - `python3 timelog_extract.py --today --narrative`
- Machine-readable JSON (quiet scan progress; pipe-friendly) and optional HTML timeline:
  - `python3 timelog_extract.py --today --format json`
  - `python3 timelog_extract.py --from 2026-04-01 --to 2026-04-30 --format json --json-file out/truth.json --report-html out/report.html`
- Custom range:
  - `python3 timelog_extract.py --from 2026-04-01 --to 2026-04-30 --source-summary`

## Config Naming (recommended)

- Use `match_terms` as the single text-matching field for project classification.
- Use `tracked_urls` for pinned AI chat URLs (Claude/Gemini and future providers).

## Cursor Extension (Scaffold)

See `cursor-extension/README.md` for build/run instructions.

## Autotests

- Run all Python autotests:
  - `./scripts/run_autotests.sh`
- Direct unittest run:
  - `python3 -m unittest discover -s tests -p "test_*.py"`
- Enforce Python source file size policy:
  - `python3 scripts/check_file_lengths.py --max-lines 500`

## File Size Policy

- Python source files should stay at or below 500 lines.
- The limit is enforced in CI via `scripts/check_file_lengths.py`.
- If a module grows too large, split by responsibility (for example: cli/config/events/analytics/pipeline).

## Accuracy Evaluation

- Plan and KPI targets: `docs/ACCURACY_PLAN.md`
- Run evaluation (requires your own prediction + golden JSON arrays):
  - `python3 scripts/eval_accuracy.py --predictions docs/evals/predictions.json --golden tests/fixtures/golden_dataset.json --output docs/evals/latest.md`

## Release Readiness

- Changelog: `CHANGELOG.md`
- License: `LICENSE`
- CI workflow: `.github/workflows/ci.yml`