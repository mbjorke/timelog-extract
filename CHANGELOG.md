# Changelog

## Unreleased

- Licensing: switched repository licensing direction to **GNU GPL-3.0** and aligned docs/metadata with open-source positioning.
- Runtime/CLI: added `--source-strategy auto|worklog-first|balanced` (phase 1). Runtime now resolves and reports effective strategy (`auto` => worklog-first when a readable worklog file exists, else balanced fallback), and JSON truth payload includes strategy/source-role metadata.
- CLI: added interactive onboarding commands:
  - `gittan setup-global-timelog` configures global git hooks (`core.hooksPath` + `post-commit`) and global ignore (`core.excludesFile`) for automatic repo-local `TIMELOG.md` entries (`--dry-run` supported).
  - `gittan setup` runs a full setup wizard (environment/PATH checks, optional global timelog automation, minimal `timelog_projects.json` bootstrap, doctor run, and optional smoke test).
  - Global timelog setup now supports choosing timelog filename/path inside each repo and optional repo-scoped logging by scanning and selecting git repositories.
- Tooling: `scripts/manual_matrix_automation.py` — partial automation for `docs/MANUAL_TEST_MATRIX_0_2_x.md` (`--deterministic` seeded worklog; `--last-month` + `QA_MATRIX_MIN_EVENTS` for calendar-month smoke against a repo root). Docs and `docs/VISION_DOCUMENTS.md` updated.
- Tooling: **golden dataset** baseline (`tests/fixtures/golden_*.json`, `tests/fixtures/golden_TIMELOG.md`) and `scripts/run_golden_eval.py` — compares expected per-(date, project) hours; writes `docs/evals/latest.md`. See `docs/ACCURACY_PLAN.md`. Test: `tests/test_golden_eval.py`.

## 0.2.1 - 2026-04-12

- **Package version 0.2.1** — documentation and GTM housekeeping; maintainer checklist: `docs/VERSIONING.md`.
- Distribution: **PyPI publication** planned for a near release (target **0.2.3**) so end users can run `pip install timelog-extract` instead of cloning and using `pip install -e .` only. README Quick Start and `docs/VERSIONING.md` describe the plan until upload.
- Docs: optional **ActivityWatch** integration backlog (`docs/ACTIVITYWATCH_INTEGRATION.md`); linked from `docs/VISION_DOCUMENTS.md` and deferred list in `docs/V1_SCOPE.md`.
- Docs: manual QA matrix for **0.2.x** (`docs/MANUAL_TEST_MATRIX_0_2_x.md`); indexed in `docs/VISION_DOCUMENTS.md`.
- Docs: **sources and flags** (`docs/SOURCES_AND_FLAGS.md`); linked from `README.md` and `docs/VISION_DOCUMENTS.md`.
- Docs: **AI-assisted project config** vision (`docs/AI_ASSISTED_CONFIG.md`); indexed in `docs/VISION_DOCUMENTS.md` and `README.md`.
- Docs: `**BRANCH.md`** — `main` is branch-protected; use feature branches + PR. Linked from `README.md`, `AGENTS.md`.
- Docs: **`docs/CI.md`** — CI overview, branch protection, and workflow; `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/VISION_DOCUMENTS.md` updated for definitive wording.
- Docs: `**docs/OPPORTUNITIES.md**` (product/GTM working notes) and `**docs/PRIVATE_LOCAL_NOTES.md**`; gitignore `**private/**` for local business-only files. **OPPORTUNITIES** also lists maintainer links for **GitHub Funding** (`.github/FUNDING.yml`), **Discussions** (announcements), **issue templates**, and **Social preview** (Open Graph sizes); `**repository-open-graph-template.png`** (1280×640) at repo root as the template asset (upload a finalized image in GitHub Settings when a logo exists).

## 0.2.0 - 2026-04-11

- **Package version 0.2.0** — merge to `main` with large CLI-first and licensing changes; maintainer checklist for future bumps: `docs/VERSIONING.md`.
- Core: inclusive preset ranges for last 3/7/14/30 days (`report_runtime`, `cli_prompts`, `status`); `--quiet` collection now fills `collector_status` like non-quiet runs; `gittan status` exits non-zero on report errors and guards missing date range.
- CLI: `gittan doctor` checks default config/worklog under **repo root** (not CWD); `sources` passes all timeframe presets into `TimelogRunOptions`; `projects` exits on JSON read/parse errors; `as_run_options` rejects unknown keys (fail fast).
- Code review follow-up: Ruff-safe `get_source_color`, canonical PyPI classifier `License :: Other/Proprietary License`, sorted `core.cli.__all__`, `VISION.md` roadmap wording for cloud agents, `V1_TAG_ANNOTATION_DRAFT.md` payload version label, `gui_preview.html` label `for=` attributes, test import from `cli_options`, ASCII hyphen in banner tagline, `SPONSORSHIP_TERMS` Patreon URL note.
- License: **Sponsorship Terms** in `LICENSE` now pin to the **same repo revision** you received (commit/tag/archive), not a moving branch tip — addresses review feedback about deterministic terms; `SPONSORSHIP_TERMS.md` version header + `LICENSE_GOALS.md` note on reviewability.
- Terminal: ASCII **Gittan** banner (`outputs/gittan_banner.py`) — playful “feeds the review rabbit” header above the report panel.
- CI: use `typing.Annotated` from the stdlib in CLI modules (Python 3.9+) instead of `typing_extensions`, which is not a declared dependency.
- Docs: `LICENSE_GOALS.md` (license intent); vision updates — **local-first** reframed to allow optional **cloud-agent** metadata via user-approved connectors; **10× / one-year** sustainability bar noted in `PATREON_POSITIONING.md`.
- Docs: `LICENSE_DECISION_MATRIX.md` (MIT / Apache / AGPL / Elastic vs Gittan).
- Docs: `V1_SCOPE.md` — **cloud-agent platform connectors** explicitly **post-v1 / backlog** so vision copy does not imply shipped scope.
- **License:** Replaced MIT with the **Gittan / Timelog Extract License** (copyright Blueberry Maybe Ab Ltd): source-available terms; professional use by **more than two persons** per organization/engagement (rolling 30 days) requires **Patreon** at the tier in `docs/SPONSORSHIP_TERMS.md`. Future releases may use different terms (`LICENSE` section 5).
- Terminal/PDF: English report output across terminal summary and invoice PDF labels; session preview shows **at least one line per source** when possible (then fills to 5 lines). See `docs/TERMINAL_I18N.md` for remaining i18n backlog.
- CLI: optional **GitHub** source — public user events (`/users/{login}/events/public`) when `--github-source on` or `auto` with `--github-user` / `GITHUB_USER`; optional `GITHUB_TOKEN` for rate limits. Sparse for old ranges (API keeps ~300 recent events). HTTP `User-Agent` uses the installed package version.
- Docs: incident write-up `docs/incidents/2026-04-09-timelog-timestamp.md`; regression test `tests/test_agents_timelog_policy.py` locks TIMELOG clock-time rules in `AGENTS.md`.
- CLI: `--format json` emits a versioned truth payload (sessions + events + metadata) to stdout; `--json-file`, `--report-html`, and `--quiet` supported. HTML report is a single self-contained file with an embedded payload.
- CLI: `--narrative` prints a rule-based executive summary in English after the report (local, no LLM).
- CLI: `-V` / `--version` prints `timelog-extract` and the package version from metadata (fallback `0.2.0-dev` when not installed).

## 1.0.0 - Draft (CLI-first)

Why this release matters:

- makes local-first AI-era time reconstruction practical via one reliable CLI/script flow,
- provides a stable engine API payload contract (`schema: timelog_extract.truth_payload`, `version: 1`),
- keeps optional extension UX separate from core v1 reporting reliability.

## 0.1.0 - 2026-04-08

- Added pre-phase agentic code evaluation report in `docs/AGENTIC_EVALUATION.md`.
- Simplified core orchestration in `timelog_extract.py`:
  - `collect_all_events()`
  - `filter_included_events()`
  - centralized invoice output path helper.
- Added Phase 0 friend-trial runner and feedback template.
- Added GUI-first Cursor extension scaffold with setup wizard and run commands.
- Added scope and privacy/security docs for public release planning.
- Added baseline CI workflow and repository README/license/changelog.
- Added dedicated CI unittest step running `scripts/run_autotests.sh` after smoke run.
- Added module/class/test-method docstrings in compatibility tests for clearer coverage.
