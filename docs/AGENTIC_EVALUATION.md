# Agentic Code Evaluation

This evaluation captures simplification opportunities before productization and plugin work.

## High-Value Simplifications Applied

- Refactored repeated event collector flow in `timelog_extract.py` into `collect_all_events()`.
- Refactored duplicated filtering logic into `filter_included_events()`.
- Replaced duplicated Chrome epoch constant usage with `CHROME_EPOCH_DELTA_US`.
- Centralized invoice output naming with `default_invoice_pdf_path()`.

These changes reduce branching and repeated code in `main()`, making a plugin bridge easier to maintain.

## Complexity Hotspots

- `timelog_extract.py` still combines:
  - source adapters (filesystem/sql parsers),
  - normalization/classification logic,
  - time/session estimation,
  - terminal report rendering,
  - PDF rendering,
  - CLI orchestration.
- This single-file architecture is workable for local use, but increases risk for plugin evolution.

## Recommended Next Refactor Cuts

1. `collectors/` module split by source family (partially done):
  - `collectors/chrome.py` (done)
  - `collectors/timelog.py` (done)
  - `collectors/cursor.py` (done)
  - `collectors/ai_logs.py` (done)
  - `collectors/mail.py` (done)
2. `core/` domain module (partially done):
  - event model and dedupe
  - project classification (done)
  - sessionization and billing math (done)
3. `outputs/` module (done):
  - terminal report rendering (done)
  - invoice PDF rendering (done)
4. thin CLI entrypoint (remaining):
  - parse args
  - call service boundary
  - print/exit

## Public-Ready Core Boundary

Expose a stable interface used by both CLI and extension:

- `run_timelog_report(config_path, date_from, date_to, options) -> ReportPayload`
- `generate_invoice_pdf(report_payload, output_path, options) -> Path`

This avoids future plugin code depending on internal collector details.

## Risk Observations

- Privacy-sensitive collectors (Mail, Chrome history, Screen Time DB) require explicit consent gating in GUI.
- macOS path assumptions are widespread and should degrade gracefully on unsupported OSes.
- Config model is now strict on `match_terms` and `tracked_urls`; docs and examples should stay aligned with this.

## Testability Gaps

- Basic automated tests now exist for classification, session gap behavior, and billable rounding.
- No fixture-based tests for source parsers (JSONL, SQLite, Mail headers).

## Suggested Test Seed (minimum)

- Unit tests:
  - `classify_project()`
  - `compute_sessions()`
  - `billable_total_hours()`
- Integration test:
  - synthetic event list -> expected day totals and project totals.