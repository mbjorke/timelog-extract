# Changelog

## Unreleased

## 0.2.13 - 2026-04-25

- Landing/demo: `gittan.html` now uses honest private-beta positioning around local evidence, project-config onboarding, and observed/classified/approved time instead of automatic billing claims.
- Live terminal demo: deterministic mock output now supports the Agentic Dev Days flow (`gittan doctor`, `gittan report --today --source-summary`, and `gittan report --today --format json`) with Truth Standard language.
- Demo API: add a Cloudflare Worker implementation for the sandbox terminal API (`/demo/health`, `/demo/sessions`, `/demo/sessions/{id}/exec`) plus deployment runbook for `api.gittan.sh`.
- Marketing: consolidate Substack draft material into [`docs/marketing/dais-substack-article-gittan-v3.md`](docs/marketing/dais-substack-article-gittan-v3.md), add hero image brief, and remove older duplicate article drafts.
- Triage JSON: `gittan triage --json` `top_sites` now include optional local timestamp anchors (`first_seen_local`, `last_seen_local`, `sample_window_local`) for faster onboarding decisions without exposing page titles/paths.
- CLI / UX: **triage** JSON plan adds **`question`**, **`choices`**, and per-suggestion **`tags`** (mobile/inbox); new **`gittan triage-apply`** applies a validated **decisions** JSON to `timelog_projects.json` (`tracked_urls` / `match_terms`) with backup + `--dry-run`.
- Docs: [`docs/runbooks/gittan-triage-agents.md`](docs/runbooks/gittan-triage-agents.md) — triage JSON extensions + `triage-apply` contract (distinct from `triage --json` output).
- CLI / UX: `gittan jira-sync` always prints one **`Next:`** line after the summary (including successful posts and empty candidate runs); no-candidate / no-unresolved runs hint to widen the range or add issue keys in git metadata.
- Docs: [`README.md`](README.md) — optional Homebrew tap path + link to [`docs/runbooks/homebrew-tap.md`](docs/runbooks/homebrew-tap.md); [`docs/runbooks/cli-polish-backlog-for-apr29.md`](docs/runbooks/cli-polish-backlog-for-apr29.md) — recorded Apr 29 decision answers for Q1–Q4.

## 0.2.12 - 2026-04-19

- Docs: [`AGENTS.md`](AGENTS.md) + [`README.md`](README.md) — document full **worklog path resolution** (`--worklog`, config `worklog`, cwd `TIMELOG.md`, then `<current_repo_root>/TIMELOG.md` via Git); [`core/report_service.py`](core/report_service.py) uses [`runtime_workspace_root()`](core/workspace_root.py) for that repo root in reports (aligned with `gittan doctor`).
- Docs: [`docs/business/github-sponsors-profile.md`](docs/business/github-sponsors-profile.md) — "install ergonomics" wording (replace nonstandard "ergonomy").
- Docs: [`docs/marketing/dais-substack-article-gittan-v3.md`](docs/marketing/dais-substack-article-gittan-v3.md) — Data & AI Stockholm Substack draft (origin story + DAIS author guidelines checklist); [`docs/README.md`](docs/README.md) index link.
- Docs: [`docs/marketing/stage-demo-speaker-notes.md`](docs/marketing/stage-demo-speaker-notes.md) — short stage script (three sentences + install one-liners) for large-audience demos.
- Docs: [`docs/runbooks/homebrew-tap.md`](docs/runbooks/homebrew-tap.md) + [`packaging/homebrew/README.md`](packaging/homebrew/README.md) — sketch for a custom Homebrew tap (`brew tap …/gittan`) before PyPI-first demos; `brew create --python` workflow and presentation fallback.
- Docs: [`README.md`](README.md) — clearer narrative flow (intro, Documentation, Contributing, Feedback); Contributing keeps seven parallel bullets + AGENTS pointer; less telegraphic tone.
- Docs: cross-link [`docs/product/vision-documents.md`](docs/product/vision-documents.md) from [`docs/README.md`](docs/README.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`AGENTS.md`](AGENTS.md) so product precedence is discoverable from contributor entry points.
- Docs: removed **Blueberry** / parent-site references from `docs/` and neutralized [`CONTRIBUTING.md`](CONTRIBUTING.md) license line (canonical names remain in [`LICENSE`](LICENSE)); funding accounts stay in [`.github/FUNDING.yml`](.github/FUNDING.yml) only.
- Docs: branch workflow is **`task/* -> main`** (no standing `dev` on `origin`); updated [`BRANCH.md`](BRANCH.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/runbooks/ci.md`](docs/runbooks/ci.md), [`AGENTS.md`](AGENTS.md), task prompts; [`docs/decisions/main-dev-branch-protection-and-release-gate.md`](docs/decisions/main-dev-branch-protection-and-release-gate.md) marked superseded in part; [`docs/runbooks/dev-main-alignment.md`](docs/runbooks/dev-main-alignment.md) scoped to forks / if `dev` is reintroduced.
- Docs: [`README.md`](README.md) — tighter structure (quick install, first run, docs index); test gate `bash scripts/run_autotests.sh`; no sponsor/parent-company copy (funding remains in [`.github/FUNDING.yml`](.github/FUNDING.yml) only).

## 0.2.11 - 2026-04-18

- Docs: Screen Time gap runbook ([`docs/runbooks/screen-time-gap-analysis.md`](docs/runbooks/screen-time-gap-analysis.md)); working notes ([`docs/product/future-notes-2026-04.md`](docs/product/future-notes-2026-04.md)) — AI help scope, calibration staging, Jira-style timestamp / analytics ideas, integration-layer licensing notes; [`docs/product/accuracy-plan.md`](docs/product/accuracy-plan.md) and [`docs/product/vision-documents.md`](docs/product/vision-documents.md) updated; README documentation map extended.
- CLI / UX: Realign [`outputs/terminal_theme.py`](outputs/terminal_theme.py), [`outputs/terminal.py`](outputs/terminal.py), [`outputs/cli_heroes.py`](outputs/cli_heroes.py) with [`docs/product/terminal-style-guide.md`](docs/product/terminal-style-guide.md) — calm lavender hierarchy and shared tokens; table `header_style` and doctor status line use [`STYLE_LABEL`](outputs/terminal_theme.py) instead of hardcoded accent hex; command heroes use `STYLE_LABEL` + `STYLE_MUTED` tagline.
- Docs: agent review contract ([`docs/decisions/agent-review-contract.md`](docs/decisions/agent-review-contract.md)) — CodeRabbit vs executor scope, Gittan path bounds, GitHub Copilot CLI remote (`copilot --remote`) pointers; [`AGENTS.md`](AGENTS.md) cross-link.
- Changelog: backfill missing [**0.2.5**](https://github.com/mbjorke/timelog-extract/pull/48) section for **0.2.x** continuity.

## 0.2.10 - 2026-04-16

- Calibration: added deterministic A/B/C experiment harness for CI (`core/cli_experiments.py`, `scripts/run_cli_experiments_ci.py`) with fixture scorecards and a report-only `cli-experiments` CI job.
- Reconciliation: added March invoice reconciliation and unified calibration reports (`core/march_reconciliation.py`, `core/march_calibration.py`, `scripts/run_march_reconciliation.py`, `scripts/run_march_calibration_report.py`) including grouped invoice support for customer-level invoice rows.
- Screen Time analysis: introduced dedicated gap analysis (`core/screen_time_gap_analysis.py`, `scripts/run_screen_time_gap_analysis.py`) with day-level coverage metrics and project-allocated signed gaps.
- Demo/Copilot hardening: fixed remaining CodeRabbit findings for demo HTTP request-body validation, Copilot CLI log collector resilience, deterministic Copilot tests, and screen-time coverage edge cases.
- Docs/ops: expanded calibration and release workflow docs and reinforced low copy-paste maintainer flow and agent quality gates.

## 0.2.9 - 2026-04-16

- CLI / UX: command heroes (`outputs/cli_heroes.py`), `ux-heroes` subcommand, shared terminal theme usage; decision docs under `docs/decisions/` (CLI UX guidelines, Copilot terminal reference); post-commit hook script split into `core/global_timelog_hook_script.py` (500-line policy).
- DX: `.cursor/rules/pre-push-quality-gate.mdc` (always-on) + `AGENTS.md` fast-path step 6 — run `run_autotests.sh` (and optional CodeRabbit CLI) before `git push`; optional `scripts/git-hooks/pre-push.sample`.
- Live terminal sandbox **P0:** `core/live_terminal_demo_contract.py` — frozen allowlist + `DEMO_SANDBOX_DENIED_MESSAGE` for the public demo (spec § Command contract).
- Live terminal sandbox **P1:** stdlib HTTP sketch — `POST /demo/sessions`, `POST /demo/sessions/<id>/exec` (JSON `{"line":...}`), `GET /demo/health`; allowlist enforced in `demo_exec_line`; deterministic stub output only (`python3 scripts/live_terminal_demo_server.py`).
- Collectors: **GitHub Copilot CLI** — reads timestamp lines from `~/.copilot/logs` (or `COPILOT_HOME`); `gittan doctor` shows directory/log status.
- Tooling: `scripts/cli_impact_smoke.sh` bundles the default agent inline CLI smoke loop (`-V`, `report --today --source-summary --quiet`, `ux-heroes`).
- Docs: `docs/live-terminal-sandbox/README.md` phase checklist for the public live-terminal demo (see spec cross-link).

## 0.2.8 - 2026-04-15

- CLI: **A/B rule suggestions** from uncategorized clusters — `gittan suggest-rules --project "…"` (preview + writes `timelog_projects.ab-suggestions.json`), `gittan apply-suggestions --option A|B [--confirm]`, and `gittan review --uncategorized --ab-suggestions` (optional interactive apply). Option **A** prefers strong URL/domain anchors and low-ambiguity repeated terms; **B** adds medium-confidence and route-style tokens. Impact preview shows +events, +hours, and uncategorized delta; config writes require confirmation and use a timestamped backup plus `save_projects_config_payload`.
- Classification: `tracked_urls` fragments now contribute to `classify_project` scoring when they appear in the same haystack as match terms (e.g. Chrome `url` + `title`), so suggested domains affect reports consistently.
- Collect **Lovable Desktop** activity from app-local storage on macOS: prefer Chromium `History` when present, and fall back to Local/Session/IndexedDB signal files when `History` is absent (still respects `--chrome-source`; classification remains URL/title-based).
- Site: removed the mock/live-replay terminal block from `gittan.html` to prioritize stable readability while a secure live terminal architecture is implemented.
- Docs: added `docs/specs/live-terminal-sandbox-demo.md` describing a deployable, allowlisted sandbox terminal design for interactive website demos.
- Site branding: favicon delivery now includes explicit `favicon-16x16.png` and `favicon-32x32.png` links/assets in addition to ICO fallback for broader client compatibility.

## 0.2.7 - 2026-04-14

- Setup UX: improved repository scope wording in `gittan setup` to reduce decision friction:
  - `All repositories (fastest, recommended)`
  - `Choose specific repositories (slower, advanced)`
- Setup UX: added clear scan progress output for the "scan and choose" flow, including per-root candidate counts and a scan-complete summary.
- Setup UX safety: when scan finds no repos, setup now shows a clear fallback message and continues safely with all-repositories scope (no perceived dead-end).
- Discovery filtering: tightened repository scan filtering to skip obvious noise/internal paths such as `.claude`, `.tmp`, `.cache`, `worktrees`, `vendor`, `imports/import`, and temp/cache variants.
- Discovery quality: avoid confusing nested duplicates where a parent repository already covers a nested path.
- Discovery robustness: repository scan now gracefully handles permission errors while traversing directories.
- Tests: expanded setup/discovery regression coverage in `tests/test_setup_repo_bootstrap.py` and added new setup selection UX tests in `tests/test_setup_scope_selection.py`.

## 0.2.6 - 2026-04-14

- Docs: `**docs/contributing/agent-task-handover-prompt.md`** — copy-paste **release-candidate / onboarding** agent prompt (RC tag format, PyPI tag workflow caveat, worktrees, `coderabbit review`, `gh pr` deduplication, A/B notes). `**AGENTS.md`**: link to that doc; **CodeRabbit CLI** examples updated to `coderabbit review --base main`.
- CI: `**static.yml`** — minimal workflow `permissions`; `**pages: write`** + `**id-token: write**` only on `**deploy**`. Shared site build in `**scripts/prepare_static_site.sh**` (verify + deploy). `**gittan doctor**`: shell-agnostic PATH hints; narrow `**except**` + `**logging**` when probing pip `--user` bin.
- Docs: **user feedback** via **[GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions)** (`README.md`, `CONTRIBUTING.md`, `docs/ideas/opportunities.md`, `docs/business/linkedin-pilot-posts.md`) — replaces removed `friend_trial/FEEDBACK_TEMPLATE.md`.
- UX: `**gittan doctor`** now reports **CLI / PATH** (`gittan` on `PATH`, pip `--user` bin, pipx `~/.local/bin`) with copy-paste **export** / **pipx ensurepath** hints. README + `**gittan.html`** recommend **pipx** first on macOS to reduce “command not found: gittan” after install.
- Onboarding: `gittan doctor` now ends with concrete next steps based on the current machine state, including when to run `gittan setup`, `gittan projects`, `pipx ensurepath`, or a first `gittan report --today --source-summary`.
- Onboarding: `gittan setup` now ends with copyable next steps after the summary table so the user can move directly from dry-run or setup completion to a useful first report.
- Onboarding: project bootstrap is now Git-aware when `gittan setup` has to create `timelog_projects.json`, seeding project name, customer, and starter `match_terms` from the local repo and `origin` remote when available.
- Diagnostics: `gittan doctor` now warns when the current repo's Git cues are not covered by any configured project's `match_terms`, with suggested terms to add in `gittan projects`.
- Tests: regression coverage for onboarding next-step guidance in both helper-level unit tests and CLI smoke tests.
- CI: GitHub Pages — PRs to `main` run `**verify-static-site`** when landing-page assets change; **production deploy** remains **push to `main`** or `**workflow_dispatch**`. Docs: `**docs/runbooks/ci.md**`, `**AGENTS.md**` (why PRs show “not deployed” until merge). **AGENTS.md:** CodeRabbit **hourly review** limits and when to use CLI vs `@coderabbitai`.
- Site: `**gittan.html`** quick start aligned with `**README.md**` (PyPI `pip install`, pipx / editable fallback, `setup --dry-run`, first report `--source-summary`); removed misleading “under 60 seconds” vs 2-minute wizard contradiction. Tests: `**test_quick_start_cli_commands_finish_within_60_seconds_each**` (`tests/test_cli_regression_smoke.py`) — after install, `-V`, `setup --dry-run`, and `doctor` each complete within **60s** (pip install timed separately via CI **package** job).
- Removed **Phase 0 friend trial** scaffolding: `**scripts/friend_trial.py`**, `**friend_trial/FEEDBACK_TEMPLATE.md**`, and the `**timelog-friend-trial**` console script entry (`pyproject.toml`). README / `**docs/product/terminal-i18n.md**` updated.

## 0.2.5 - 2026-04-14

- Historical release backfill: this line tracks the tagged `v0.2.5` release point between `v0.2.3` and the later onboarding/setup series.
- Release prep: finalized `0.2.5rc1` onboarding guidance and related docs polish before the `0.2.6` onboarding improvements.
- PyPI/onboarding continuity: carried forward the `0.2.4` metadata and PATH guidance improvements that made installation and first-run doctor/setup flows more predictable.

## 0.2.4 - 2026-04-13

- **PyPI project page:** README hero image now uses a stable `**raw.githubusercontent.com`** URL so the logo renders on [the PyPI description](https://pypi.org/project/timelog-extract/) (relative paths do not work there). Added `**[project.urls]**` — `Homepage` (**gittan.sh**), `Repository`, `Issues`.

## 0.2.3 - 2026-04-13

- **Package version 0.2.3** — first **PyPI upload** milestone: maintainers publish sdist + wheel via GitHub Actions (tag `v0.2.3` or manual workflow run) after [trusted publishing](https://docs.pypi.org/trusted-publishers/) is configured for this repository.
- CI: new **package** job builds sdist/wheel with `python -m build` and smoke-installs the wheel (`timelog-extract -V`, `gittan -V`).
- Packaging: include the `**outputs`** package in the wheel/sdist (`setuptools` `packages.find`) so installed CLIs import `outputs.terminal_theme` and related modules.
- Docs: `docs/runbooks/versioning.md` and `docs/runbooks/ci.md` updated for the publish workflow.
- README: reorganized — **install** (`pipx` / `pip` / editable clone) at the top, short **get started**, command cheat sheet, compact troubleshooting; removed the long inline doc inventory (see `docs/product/vision-documents.md`).
- **Brand / site:** **Rabbit-v2** canonical masters; removed **steward** / **rabbit-pot** / `**variants/`** experiments. `**gittan-logo.png**` at repo root (768×768 square crop, pixel-crisp) for `**gittan.html**` hero and social/preview use; **nav** uses a two-part mark — mini **terminal review rabbit** (same beats as the demo: `(\/)` → `(..)` → `><` → `\`, staggered CSS reveal, respects `prefers-reduced-motion`) plus a **pixel-style wordmark** (Press Start 2P). `scripts/build_brand_assets.sh` generates favicon, README icon, `gittan-logo.png`, `og-image.png`; Pages workflow publishes the static assets. Docs: `docs/brand/README.md`, `IDENTITY.md`, `VISION_DOCUMENTS.md`, root `README.md`, `**outputs/gittan_banner.py`** docstring.

## 0.2.2 - 2026-04-13

- Setup safety: `gittan setup` now treats malformed `timelog_projects.json` as recoverable state, creates a timestamped backup (`timelog_projects.backup-YYYYMMDD-HHMMSS.json`), and only then recreates a minimal config.
- Tests: added setup regression coverage for valid-config keep behavior and invalid-config backup/recreate flow (`tests/test_setup_projects_config.py`).
- Docs/policy: clarified role split where `TIMELOG.md` remains human-readable local work journal while `timelog_projects.json` is critical configuration that should have an external backup.
- Pages/social: added site assets `favicon.ico` and `og-image.png`, added Open Graph/Twitter/fav icon meta tags in `gittan.html`, and updated Pages workflow to publish the assets.
- Versioning: moved release line to **0.2.2** and dev fallback to `0.2.2-dev` (`pyproject.toml`, `core/cli_options.py`).

## 0.2.1 - 2026-04-12

- **Package version 0.2.1** — documentation and GTM housekeeping; maintainer checklist: `docs/runbooks/versioning.md`.
- Distribution: **PyPI publication** planned for a near release (target **0.2.3**) so end users can run `pip install timelog-extract` instead of cloning and using `pip install -e .` only. README Quick Start and `docs/runbooks/versioning.md` describe the plan until upload.
- Docs: optional **ActivityWatch** integration backlog (`docs/sources/activitywatch-integration.md`); linked from `docs/product/vision-documents.md` and deferred list in `docs/product/v1-scope.md`.
- Docs: manual QA matrix for **0.2.x** (`docs/runbooks/manual-test-matrix-0-2-x.md`); indexed in `docs/product/vision-documents.md`.
- Docs: **sources and flags** (`docs/sources/sources-and-flags.md`); linked from `README.md` and `docs/product/vision-documents.md`.
- Docs: **AI-assisted project config** vision (`docs/sources/ai-assisted-config.md`); indexed in `docs/product/vision-documents.md` and `README.md`.
- Docs: `**BRANCH.md`** — `main` is branch-protected; use feature branches + PR. Linked from `README.md`, `AGENTS.md`.
- Docs: `**docs/runbooks/ci.md`** — CI overview, branch protection, and workflow; `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/product/vision-documents.md` updated for definitive wording.
- Docs: `**docs/ideas/opportunities.md`** (product/GTM working notes) and `**docs/meta/private-local-notes.md**`; gitignore `**private/**` for local business-only files. **OPPORTUNITIES** also lists maintainer links for **GitHub Funding** (`.github/FUNDING.yml`), **Discussions** (announcements), **issue templates**, and **Social preview** (Open Graph sizes); `**repository-open-graph-template.png`** (1280×640) at repo root as the template asset (upload a finalized image in GitHub Settings when a logo exists).

## 0.2.0 - 2026-04-11

- **Package version 0.2.0** — merge to `main` with large CLI-first and licensing changes; maintainer checklist for future bumps: `docs/runbooks/versioning.md`.
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
- Terminal/PDF: English report output across terminal summary and invoice PDF labels; session preview shows **at least one line per source** when possible (then fills to 5 lines). See `docs/product/terminal-i18n.md` for remaining i18n backlog.
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

- Added pre-phase agentic code evaluation report in `docs/legacy/agentic-evaluation.md`.
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