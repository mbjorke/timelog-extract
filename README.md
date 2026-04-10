# Timelog Extract

Timelog Extract aggregates local activity signals into project/customer time reports and optional invoice PDFs.

## Current Deliverables

- Refactored CLI core in `timelog_extract.py` with cleaner orchestration.
- Phase 0 friend-trial runner: `scripts/friend_trial.py`.
- GUI-first Cursor extension scaffold in `cursor-extension/`.
- Productization docs in `docs/`:
  - `GITTAN_VISION.md`
  - `GITTAN_VISION_EN.md`
  - `GITTAN_NORTHSTAR_METRICS.md`
  - `AGENTIC_EVALUATION.md`
  - `CASE_STUDY.md`
  - `CASE_STUDY_TECH.md`
  - `V1_SCOPE.md`
  - `V1_FINISH_PLAN.md`
  - `PRIVACY_SECURITY.md`
  - `SIMILAR_REPOS_CHECKLIST.md`
  - `TERMINAL_I18N.md` (English UI backlog; terminal output is English)

## Quick Start (Friend Trial)

1. Create/activate Python 3.9+ environment.
2. Install dependencies:
  - `python3 -m pip install -e .`
3. Run:
  - `python3 scripts/friend_trial.py --today --invoice-pdf`
4. Share feedback in `friend_trial/FEEDBACK_TEMPLATE.md`.

## CLI Usage

- **Use it now (recommended, no Cursor debug setup needed):**
  - `python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json`
  - This uses the same `core.engine_api` boundary as the extension.
  - You should see `schema`, `version`, `totals`, plus `pdf_path` when `--pdf` is enabled.

- Today:
  - `python3 timelog_extract.py --today --source-summary --invoice-pdf`
- Same with a plain-English executive blurb after the tables (rule-based, offline):
  - `python3 timelog_extract.py --today --narrative`
- Worklog formats:
  - Default path is `<current_repo_root>/TIMELOG.md` — i.e. the root of the repository where you run the command (Markdown headings like `## YYYY-MM-DD HH:MM`).
  - Also supports gtimelog-style text logs with lines like `YYYY-MM-DD HH:MM: summary`.
  - Use `--worklog PATH` to point at a different file and `--worklog-format {auto,md,gtimelog}` to force a format (default: `auto`).
  - **Path precedence (important):**
    1. If `--worklog PATH` is provided, that path is used.
    2. Else if `worklog` is set in workspace config (`timelog_projects.json`), that path is used.
    3. Otherwise, `<current_repo_root>/TIMELOG.md` is used.
  - Human examples:
    - Repo default: `python3 timelog_extract.py --today`
    - Custom file in repo: `python3 timelog_extract.py --today --worklog ./.private/my-worklog.md --worklog-format md`
    - Centralized personal log: `python3 timelog_extract.py --today --worklog ~/timelogs/all-repos.md --worklog-format md`
    - gtimelog text file: `python3 timelog_extract.py --today --worklog ~/timelogs/timelog.txt --worklog-format gtimelog`
  - Agent resolution algorithm:
    1. If user/command provides `--worklog`, use it.
    2. Else if workspace config contains `worklog`, use it.
    3. Else use `<current_repo_root>/TIMELOG.md`.
    4. If chosen file is missing, create it.
- Machine-readable JSON (quiet scan progress; pipe-friendly) and optional HTML timeline:
  - `python3 timelog_extract.py --today --format json`
  - `python3 timelog_extract.py --from 2026-04-01 --to 2026-04-30 --format json --json-file out/truth.json --report-html out/report.html`
- GitHub public activity (optional): set `--github-user YOUR_LOGIN` or `GITHUB_USER`, optionally `GITHUB_TOKEN` for API rate limits; use `--github-source on` to require it, or `auto` (default) to enable when a username is set.
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