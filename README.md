# Timelog Extract

Timelog Extract aggregates local activity signals into project/customer time reports and optional invoice PDFs.
All processing is local-only in the core v1 CLI flow (no cloud upload path).

## Current Deliverables

- Refactored CLI core in `timelog_extract.py` with cleaner orchestration.
- Phase 0 friend-trial runner: `scripts/friend_trial.py`.
- GUI-first Cursor extension scaffold in `cursor-extension/`.
- Productization docs in `docs/`:
  - `VISION_DOCUMENTS.md` (how `VISION.md` relates to the GITTAN_* docs — **read this when editing vision copy**)
  - `GITTAN_VISION.md`
  - `GITTAN_VISION_EN.md`
  - `GITTAN_NORTHSTAR_METRICS.md`
  - `AGENTIC_EVALUATION.md`
  - `CASE_STUDY.md`
  - `CASE_STUDY_TECH.md`
  - `V1_SCOPE.md`
  - `V1_FINISH_PLAN.md`
  - `PRIVACY_SECURITY.md`
  - `SPONSORSHIP_TERMS.md` (legacy sponsorship notes; not a license gate under GPL)
  - `LICENSE_GOALS.md` (why GPL-3.0 fits the project strategy)
  - `SIMILAR_REPOS_CHECKLIST.md`
  - `TERMINAL_I18N.md` (English UI backlog; terminal output is English)
  - `TERMINAL_STYLE_GUIDE.md` (CLI visual semantics: typography, color roles, and low-noise layout rules)
  - `SOURCES_AND_FLAGS.md` (how source toggles and `--exclude` relate to collection — **not** a filter on one shared dataset)
  - `AI_ASSISTED_CONFIG.md` (vision: future in-product assistant for project JSON — names first, optional LLM, privacy notes)
  - `OPPORTUNITIES.md` (product / go-to-market working notes — for business-style review)
  - `GITHUB_SPONSORS_PROFILE.md` (canonical bio/introduction copy for `github.com/sponsors/blueberry-maybe`)
  - `PRIVATE_LOCAL_NOTES.md` (how to keep **gitignored** `private/` business notes outside commits)

## Quick Start (Friend Trial)

1. Create/activate Python 3.9+ environment.
2. Install dependencies:
  - `python3 -m pip install -e .` (from a clone of this repository).
  - **PyPI:** not published yet; `pip install timelog-extract` is planned for a near release (around **0.2.3**). See `docs/VERSIONING.md`.
3. Run:
  - `python3 scripts/friend_trial.py --today --invoice-pdf`
4. Share feedback in `friend_trial/FEEDBACK_TEMPLATE.md`.
5. Optional but recommended before first real usage:
  - `gittan setup-global-timelog` (interactive machine-wide setup for automatic `TIMELOG.md` entries after commits)

## CLI Usage

- **Use it now (recommended, no Cursor debug setup needed):**
  - `python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json`
  - This uses the same `core.engine_api` boundary as the extension.
  - You should see `schema`, `version`, `totals`, plus `pdf_path` when `--pdf` is enabled.
- Guided setup wizard:
  - `gittan setup` (or `python3 timelog_extract.py setup`)
  - Runs environment checks, global timelog automation, project-config bootstrap, doctor, and optional smoke report.
  - Lets you choose timelog file path inside repos (default `TIMELOG.md`) and optionally restrict logging to selected repositories.
  - Start safely with `--dry-run`; use `--yes` for non-interactive onboarding.

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
  - Source strategy:
    - `--source-strategy auto|worklog-first|balanced` (default `auto`)
    - `auto` prefers worklog-first when a readable worklog exists, otherwise falls back to balanced mode.
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
The extension is a beta companion; CLI/script workflows are the primary v1 path.

## Troubleshooting

- **Sources look empty or “0 events”:** see `docs/SOURCES_AND_FLAGS.md` (collectors vs `--exclude`, and `collector_status` in `--format json`).
- Missing Python dependencies:
  - `python3 -m pip install -e .`
- Missing project config:
  - verify `timelog_projects.json` exists, or pass `--projects-config PATH`
- File permission/path issues:
  - check read access for `--worklog`, browser history DBs, and optional Mail/Screen Time sources
- Global timelog automation setup:
  - run `gittan setup-global-timelog` (or `python3 timelog_extract.py setup-global-timelog`)
  - use `--dry-run` first if you want to preview changes
  - full manual fallback guide: `GLOBAL_TIMELOG_AUTOMATION.md`

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

## Contributing

- See [`CONTRIBUTING.md`](CONTRIBUTING.md) (PRs: **English** title and description; tests and line-limit policy).
- **`main` is branch-protected:** no direct pushes — use a feature branch and PR — see [`BRANCH.md`](BRANCH.md) and [`docs/CI.md`](docs/CI.md).

## Release Readiness

- Changelog: `CHANGELOG.md`
- License: `LICENSE` (**GNU GPL-3.0-or-later**)
- CI: [`docs/CI.md`](docs/CI.md) (workflow: `.github/workflows/ci.yml`)
- CLI-first release gate: `docs/CLI_FIRST_V1_RELEASE_CHECKLIST.md`
- RC test script for second tester: `docs/RC_TEST_SCRIPT_CLI_FIRST.md`