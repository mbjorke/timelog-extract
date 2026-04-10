# V1 Finish Plan

This plan closes the final productization gap from "late beta" to a stable v1 release.

## Release Gate (must pass)

- Consent flow is explicit before any privacy-sensitive source can run.
- Source toggles are available in setup and persisted in workspace config.
- Parser fixture tests cover v1-critical collectors with CI execution.
- Extension report run path is stable for terminal/json/html/pdf flows.

## Milestones

### M1 - Trust + Setup UX (highest priority)

Goal: make consent and source control explicit, understandable, and reversible.

- Add first-run consent view with clear source categories:
  - always-on local sources (safe default)
  - privacy-sensitive optional sources (Mail, Chrome, Screen Time)
- Add per-source toggles in setup wizard and settings view.
- Persist source choices in extension workspace config.
- Show "what will be scanned" summary before first report run.
- Add lightweight copy for local-only guarantees and file locations.

Suggested file targets:

- `cursor-extension/src/webview/*`
- `cursor-extension/src/commands/*`
- `cursor-extension/src/config/*`
- `docs/PRIVACY_SECURITY.md` (consent language alignment)

Exit criteria:

- New user can install -> consent -> choose sources -> run first report without CLI edits.
- Existing user can revisit setup and change source toggles.

### M2 - Parser Hardening via Fixtures

Goal: make extractor behavior stable across known local-data variants.

- Add fixture-driven parser tests for:
  - Cursor logs/checkpoints
  - Claude CLI/Desktop logs
  - Gemini CLI logs
  - SQLite-backed collectors (Chrome/Screen Time where feasible)
- Add fixture metadata docs (source version/date, expected parsed events).
- Add CI job gating for fixture suite.

Suggested file targets:

- `tests/fixtures/*`
- `tests/test_*collector*.py`
- `.github/workflows/ci.yml`
- `docs/AGENTIC_EVALUATION.md` (update testability status)

Exit criteria:

- Fixture suite is deterministic locally and in CI.
- Failures point to a specific parser/source quickly.

### M3 - Thin Service Boundary (engine API)

Goal: keep CLI and extension calling a narrow, stable engine surface.

- Keep public engine API as:
  - `run_timelog_report(config_path, date_from, date_to, options)`
  - `generate_invoice_pdf(report_payload, output_path, options)`
- Move orchestration helpers out of monolithic service code into focused modules:
  - run context/setup
  - runtime collection
  - post-collection aggregation
- Ensure CLI layer remains a pure adapter (parse args -> service call -> output).
- Add service-boundary tests for option normalization and payload shape.

Suggested file targets:

- `core/report_service.py`
- `core/report_runtime.py` (new)
- `core/report_cli.py`
- `tests/test_service_boundary.py`

Exit criteria:

- Extension does not import collector internals.
- Service module responsibilities are clear and separately testable.

### M4 - RC + Ship

Goal: validate end-to-end behavior and ship v1 confidently.

- Create v1 RC checklist (install, setup, run, filters, exports, errors).
- Run 1-2 dogfood cycles and record defects.
- Fix only release-blocking issues.
- Update changelog and tag v1.

Suggested file targets:

- `docs/` release checklist doc
- `CHANGELOG.md`

Exit criteria:

- RC checklist passes on clean machine/workspace.
- No known P0/P1 defects in v1 scope.

## Two-Week Execution Sequence

### Week 1

- Day 1-2: M1 consent + source toggles skeleton in extension UI.
- Day 3: M1 persistence + setup summary + copy polish.
- Day 4-5: M2 fixture scaffolding + first 2 high-impact source fixtures.

### Week 2

- Day 1-2: M2 remaining fixtures + CI gating + docs updates.
- Day 3: M3 boundary cleanup and service tests.
- Day 4: M4 RC checklist run + bugfix pass.
- Day 5: final QA pass, changelog, v1 tag prep.

## Tracking Board (recommended)

Use one board with four lanes mapped to milestones: `M1`, `M2`, `M3`, `M4`.

Keep ticket templates short:

- Scope
- Acceptance criteria
- Test evidence (command/output or screenshot)
- Risk notes (privacy, parser drift, UX confusion)
