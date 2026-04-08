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
- Custom range:
  - `python3 timelog_extract.py --from 2026-04-01 --to 2026-04-30 --source-summary`

## Config Naming (recommended)

- Use `match_terms` as the single text-matching field for project classification.
- Use `tracked_urls` for pinned AI chat URLs (Claude/Gemini and future providers).
- Backward compatibility remains for old keys (`keywords`, `project_terms`, `claude_urls`, `gemini_urls`), but new configs should prefer the unified names.

## Cursor Extension (Scaffold)

See `cursor-extension/README.md` for build/run instructions.

## Autotests

- Run all Python autotests:
  - `./scripts/run_autotests.sh`
- Direct unittest run:
  - `python3 -m unittest discover -s tests -p "test_*.py"`

## Release Readiness

- Changelog: `CHANGELOG.md`
- License: `LICENSE`
- CI workflow: `.github/workflows/ci.yml`