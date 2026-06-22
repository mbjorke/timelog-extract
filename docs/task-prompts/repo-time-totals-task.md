# GH-146: `gittan status --history` — all available logs + Git estimate

> **Status (2026-06-22, locked):** `gittan status --history` runs **without a period
> prompt**, scans **all logs Gittan can still read** (wide window from 2020-01-01),
> and shows **Total (observed)** | **Git estimate** | **Sessions**. No TIMELOG
> column. Compare columns — do not add. Retention limits apply. Legacy `gittan
> status --git` keeps a **period-scoped** git column ("Git only").

## Problem

`gittan status` defaults to a selected period. Operators also need a one-shot view
of **how much evidence exists per project across retained logs**, plus an optional
**commit-derived bootstrap** when `git_repo` is configured — without mislabeling
worklog sums as "everything Gittan saw."

## Target UX

```bash
gittan status --history          # no period prompt; all available logs
gittan status --last-week --history   # optional explicit window still supported
```

| Column | Meaning | Source |
|---|---|---|
| **Total (observed)** | Hours from collectors over the report window | All enabled sources (IDE, AI, worklog, …) |
| **Git estimate** | Commit-timestamp session estimate | `git log` on profile `git_repo` (all-time when `--history`) |
| **Sessions** | Session count for observed total | Existing session math |

**Not shown:** TIMELOG (all-time) column (withdrawn — confused operators).

**Legend (under table):** *Total (observed) uses all logs Gittan can still read;
Git estimate uses commits only. Compare — do not add. Retention limits apply.*

## Behavior contract

```gherkin
Feature: status --history without period
  Scenario: Default history uses all available logs
    When the user runs "gittan status --history"
    Then no interactive period prompt appears
    And the title shows "All available logs"
    And project rows show Total (observed) and Git estimate columns

  Scenario: Git estimate needs git_repo
    Given a project profile without git_repo
    When the user runs "gittan status --history"
    Then Git estimate shows "—" for that project
    And a tip mentions configuring git_repo

  Scenario: Historical columns are display-only
    When Gittan aggregates the report
    Then session computation and billable hours for invoicing are unchanged
```

## Key files

- `core/cli_date_range.py` — `resolve_all_available_window()`, `has_explicit_date_window()`
- `core/cli_status.py` — period-less `--history`, column headers
- `core/cli_status_history.py` — git cell + legend helpers
- `core/report_historical_totals.py` — git all-time under `--history`; no TIMELOG totals
- `core/git_totals.py` — `compute_git_project_totals` (unbounded when no dt bounds)
- `outputs/terminal_history.py` — report legend + "Git estimate" label
- `outputs/terminal.py` — suppress TIMELOG column when `--history`

## Prerequisites

- Accuracy net (sanity bounds + golden composer eval) — landed.
- Shadow log replay (#158) — merged; optional `--shadow-log` extends observed retention.

## Out of scope

- Total Invoiced / billing log storage
- Replacing period `Hours` as the default status view
- TIMELOG (all-time) column under `--history`

## Traceability

- story_id: GH-146
- spec_status: approved
- implementation_status: in progress
- created_at: 2026-06-12
- last_updated_at: 2026-06-22
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/157
- implementation.branch: task/history-columns
- implementation.commits: []
- validation.evidence: `tests/test_history_columns.py`, `tests/test_report_historical_totals.py`, `tests/test_evidence_store.py`, `bash scripts/run_autotests.sh`
- validation.decision: conditional GO
- changelog:
  - 2026-06-12: Initial draft (historical columns).
  - 2026-06-15: Withdrew mislabeled "Total observed" (TIMELOG) after composer day-collapse.
  - 2026-06-22: GH-146 locked — observed all-logs + Git estimate; no TIMELOG column; no period prompt.
