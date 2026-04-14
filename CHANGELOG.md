# Changelog

## Unreleased

- Nothing yet.

## 0.2.5rc1 - 2026-04-14

- CI: **`static.yml`** — minimal workflow `permissions`; **`pages: write`** + **`id-token: write`** only on **`deploy`**. Shared site build in **`scripts/prepare_static_site.sh`** (verify + deploy). **`gittan doctor`**: shell-agnostic PATH hints; narrow **`except`** + **`logging`** when probing pip `--user` bin.
- Docs: **user feedback** via **[GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions)** (`README.md`, `CONTRIBUTING.md`, `docs/OPPORTUNITIES.md`, `docs/LINKEDIN_PILOT_POSTS.md`) — replaces removed `friend_trial/FEEDBACK_TEMPLATE.md`.
- UX: **`gittan doctor`** now reports **CLI / PATH** (`gittan` on `PATH`, pip `--user` bin, pipx `~/.local/bin`) with copy-paste **export** / **pipx ensurepath** hints. README + **`gittan.html`** recommend **pipx** first on macOS to reduce “command not found: gittan” after install.
- Onboarding: `gittan doctor` now ends with concrete next steps based on the current machine state, including when to run `gittan setup`, `gittan projects`, `pipx ensurepath`, or a first `gittan report --today --source-summary`.
- Onboarding: `gittan setup` now ends with copyable next steps after the summary table so the user can move directly from dry-run or setup completion to a useful first report.
- Tests: regression coverage for onboarding next-step guidance in both helper-level unit tests and CLI smoke tests.
- CI: GitHub Pages — PRs to `main` run **`verify-static-site`** when landing-page assets change; **production deploy** remains **push to `main`** or **`workflow_dispatch`**. Docs: **`docs/CI.md`**, **`AGENTS.md`** (why PRs show “not deployed” until merge). **AGENTS.md:** CodeRabbit **hourly review** limits and when to use CLI vs `@coderabbitai`.
- Site: **`gittan.html`** quick start aligned with **`README.md`** (PyPI `pip install`, pipx / editable fallback, `setup --dry-run`, first report `--source-summary`); removed misleading “under 60 seconds” vs 2-minute wizard contradiction. Tests: **`test_quick_start_cli_commands_finish_within_60_seconds_each`** (`tests/test_cli_regression_smoke.py`) — after install, `-V`, `setup --dry-run`, and `doctor` each complete within **60s** (pip install timed separately via CI **package** job).
- Removed **Phase 0 friend trial** scaffolding: **`scripts/friend_trial.py`**, **`friend_trial/FEEDBACK_TEMPLATE.md`**, and the **`timelog-friend-trial`** console script entry (`pyproject.toml`). README / **`docs/TERMINAL_I18N.md`** updated.

## 0.2.4 - 2026-04-13

- **PyPI project page:** README hero image now uses a stable **`raw.githubusercontent.com`** URL so the logo renders on [the PyPI description](https://pypi.org/project/timelog-extract/) (relative paths do not work there). Added **`[project.urls]`** — `Homepage` (**gittan.sh**), `Repository`, `Issues`.

## 0.2.3 - 2026-04-13

- **Package version 0.2.3** — first **PyPI upload** milestone: maintainers publish sdist + wheel via GitHub Actions (tag `v0.2.3` or manual workflow run) after [trusted publishing](https://docs.pypi.org/trusted-publishers/) is configured for this repository.
- CI: new **package** job builds sdist/wheel with `python -m build` and smoke-installs the wheel (`timelog-extract -V`, `gittan -V`).
- Packaging: include the **`outputs`** package in the wheel/sdist (`setuptools` `packages.find`) so installed CLIs import `outputs.terminal_theme` and related modules.
- Docs: `docs/VERSIONING.md` and `docs/CI.md` updated for the publish workflow.
- README: reorganized — **install** (`pipx` / `pip` / editable clone) at the top, short **get started**, command cheat sheet, compact troubleshooting; removed the long inline doc inventory (see `docs/VISION_DOCUMENTS.md`).
- **Brand / site:** **Rabbit-v2** canonical masters; removed **steward** / **rabbit-pot** / **`variants/`** experiments. **`gittan-logo.png`** at repo root (768×768 square crop, pixel-crisp) for **`gittan.html`** hero and social/preview use; **nav** uses a two-part mark — mini **terminal review rabbit** (same beats as the demo: `(\/)` → `(..)` → `><` → `\`, staggered CSS reveal, respects `prefers-reduced-motion`) plus a **pixel-style wordmark** (**Press Start 2P**). **`scripts/build_brand_assets.sh`** generates favicon, README icon, **`gittan-logo.png`**, **`og-image.png`**; Pages workflow publishes the static assets. Docs: **`docs/brand/README.md`**, **`IDENTITY.md`**, **`VISION_DOCUMENTS.md`**, root **`README.md`**, **`outputs/gittan_banner.py`** docstring.

## 0.2.2 - 2026-04-13

- Setup safety: `gittan setup` now treats malformed `timelog_projects.json` as recoverable state, creates a timestamped backup (`timelog_projects.backup-YYYYMMDD-HHMMSS.json`), and only then recreates a minimal config.
- Tests: added setup regression coverage for valid-config keep behavior and invalid-config backup/recreate flow (`tests/test_setup_projects_config.py`).
- Docs/policy: clarified role split where `TIMELOG.md` remains human-readable local work journal while `timelog_projects.json` is critical configuration that should have an external backup.
- Pages/social: added site assets `favicon.ico` and `og-image.png`, added Open Graph/Twitter/fav icon meta tags in `gittan.html`, and updated Pages workflow to publish the assets.
- Versioning: moved release line to **0.2.2** and dev fallback to `0.2.2-dev` (`pyproject.toml`, `core/cli_options.py`).

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
- Code review follow-up: Ruff-safe `get_source_color`, sorted `core.cli.__all__`, `VISION.md` roadmap wording for cloud agents, `V1_TAG_ANNOTATION_DRAFT.md` payload version label, `gui_preview.html` label `for=` attributes, test import from `cli_options`, ASCII hyphen in banner tagline, `SPONSORSHIP_TERMS` Patreon URL note.
- License: repository licensing direction is now **GNU GPL-3.0-or-later**; older source-available/sponsorship-license notes remain historical context only.
- Terminal: ASCII **Gittan** banner (`outputs/gittan_banner.py`) — playful “feeds the review rabbit” header above the report panel.
- CI: use `typing.Annotated` from the stdlib in CLI modules (Python 3.9+) instead of `typing_extensions`, which is not a declared dependency.
- Docs: `LICENSE_GOALS.md` (license intent); vision updates — **local-first** reframed to allow optional **cloud-agent** metadata via user-approved connectors; **10× / one-year** sustainability bar noted in `PATREON_POSITIONING.md`.
- Docs: `LICENSE_DECISION_MATRIX.md` (MIT / Apache / AGPL / Elastic vs Gittan).
- Docs: `V1_SCOPE.md` — **cloud-agent platform connectors** explicitly **post-v1 / backlog** so vision copy does not imply shipped scope.
- **License:** project licensing is **GNU GPL-3.0-or-later** (repository `LICENSE`).
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
