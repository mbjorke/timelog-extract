# Changelog

## Unreleased

- CI: use `typing.Annotated` from the stdlib in CLI modules (Python 3.9+) instead of `typing_extensions`, which is not a declared dependency.
- Docs: `LICENSE_GOALS.md` (license intent); vision updates — **local-first** reframed to allow optional **cloud-agent** metadata via user-approved connectors; **10× / one-year** sustainability bar noted in `PATREON_POSITIONING.md`.
- Docs: `LICENSE_DECISION_MATRIX.md` (MIT / Apache / AGPL / Elastic vs Gittan).
- Docs: `V1_SCOPE.md` — **cloud-agent platform connectors** explicitly **post-v1 / backlog** so vision copy does not imply shipped scope.
- **License:** Replaced MIT with the **Gittan / Timelog Extract License** (copyright Blueberry Maybe Ab Ltd): source-available terms; professional use by **more than two persons** per organization/engagement (rolling 30 days) requires **Patreon** at the tier in `docs/SPONSORSHIP_TERMS.md`. Future releases may use different terms (`LICENSE` section 5).
- Terminal/PDF: English report output across terminal summary and invoice PDF labels; session preview shows **at least one line per source** when possible (then fills to 5 lines). See `docs/TERMINAL_I18N.md` for remaining i18n backlog.
- CLI: optional **GitHub** source — public user events (`/users/{login}/events/public`) when `--github-source on` or `auto` with `--github-user` / `GITHUB_USER`; optional `GITHUB_TOKEN` for rate limits. Sparse for old ranges (API keeps ~300 recent events).
- Docs: incident write-up `docs/incidents/2026-04-09-timelog-timestamp.md`; regression test `tests/test_agents_timelog_policy.py` locks TIMELOG clock-time rules in `AGENTS.md`.
- CLI: `--format json` emits a versioned truth payload (sessions + events + metadata) to stdout; `--json-file`, `--report-html`, and `--quiet` supported. HTML report is a single self-contained file with an embedded payload.
- CLI: `--narrative` prints a rule-based executive summary in English after the report (local, no LLM).
- CLI: `-V` / `--version` prints `timelog-extract` and the package version from metadata (fallback `0.1.0-dev` when not installed).

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