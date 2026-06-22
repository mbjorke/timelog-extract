# GH-146: `gittan status --history` — period Hours + comparison columns

> **Status (2026-06-22, locked):** `--history` adds **Total (observed)** and **Git
> estimate** beside period **Hours**. Period selection is unchanged (prompt,
> `--last-month`, `--from`/`--to`, etc.). No TIMELOG column. Compare — do not add.

## Problem

`gittan status` defaults to a selected period. Operators also need a one-shot view
of **how much evidence exists per project across retained logs**, plus an optional
**commit-derived bootstrap** when `git_repo` is configured — without mislabeling
worklog sums as "everything Gittan saw."

## Target UX

```bash
gittan status --last-month --history
gittan status --from 2026-06-01 --to 2026-06-15 --history
```

| Column | Meaning | Window |
|---|---|---|
| **Hours** | Period total from collectors | Selected period |
| **Total (observed)** | Retained evidence magnitude | All available logs (2020-01-01 → today) |
| **Git estimate** | Commit-timestamp sessions | All-time (`git_repo`) |
| **Sessions** | Period session count | Selected period |

**Not shown:** TIMELOG (all-time) column.

**Legend:** Hours are for the selected period. Total (observed) and Git estimate are
for comparison only — do not add them to Hours.

## Behavior contract

```gherkin
Feature: status --history with period
  Scenario: History adds columns beside period Hours
    When the user runs "gittan status --last-month --history"
    Then the table shows Hours for the last month
    And Total (observed) and Git estimate columns appear
    And period selection was not skipped

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

- `core/report_observed_totals.py` — second collector pass for all-available observed totals
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
