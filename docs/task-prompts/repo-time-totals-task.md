# Per-project totals in gittan status: Total observed + Git-only columns

## Problem

`gittan status` and `gittan report` show hours for the **selected period only**.
There is no quick way to see total accumulated time per project across all
history, or to bootstrap a time estimate from git commit history for new users
who have not yet built up a full Gittan event log.

A beta tester request surfaced two distinct needs:

1. **Total observed** — how many hours Gittan has recorded for a project across
   all time, not just the current window. Useful as a sanity check ("does this
   project really have only 10 hours total?") and as an onboarding value:
   TIMELOG.md history is available from day one.

2. **Git-only** — a secondary column derived purely from `git log` timestamps,
   surfaced transparently as a comparison signal. Accuracy varies by workflow
   (Lovable/Claude Code auto-commit workflows can reach 70–90%); it is never
   treated as a primary estimate. New users get immediate historical coverage
   without waiting to accumulate IDE/AI event logs.

**Out of scope for this story:** Total Invoiced (requires new billing log
storage — own story).

## Prerequisite

[PR #144](https://github.com/mbjorke/timelog-extract/pull/144) (merged) —
`core/repo_slug.py` provides cached path→`owner/repo` slug resolution that the
git-only collector reuses for project attribution.

## Proposed columns in gittan status

| Column | Source | Always shown |
|---|---|---|
| This period | Existing report engine | Yes |
| Total observed | TIMELOG.md all-time sum | Yes (P1) |
| Git only | `git log` per configured repo | No — requires `--git` flag (P2) |

## P1 — Total observed column

### Task

Add a **Total observed** column to `gittan status` that sums all TIMELOG.md
entries per project without date filtering, displayed next to the period hours.

### Key files

- `core/timelog_totals.py` — all-time TIMELOG.md aggregation (iterates all worklog paths)
- `core/git_totals.py` — per-profile git log aggregation using passive session floor
- `collectors/git_commits.py` — git log timestamp reader
- `core/report_service.py` — orchestration; computes and passes totals to ReportPayload
- `core/report_cli.py` — wires totals to terminal output
- `outputs/terminal.py` — "Total observed" and "Git only" columns in breakdown table

### Non-goals (P1)

- Do not include IDE/AI rolling-window events in the total — their retention
  window is bounded; TIMELOG.md is the only source with reliable all-time history.
- Do not change how period hours are calculated.

## Behavior Contract (P1)

```gherkin
Feature: Total observed column in gittan status
  Users see accumulated project hours across all TIMELOG.md history
  alongside the current period, without changing report accuracy.

  Background:
    Given TIMELOG.md contains entries across multiple months for Project Alpha
    And the user runs gittan for a one-week period

  Scenario: Total observed shown alongside period hours
    Given Project Alpha has 3h in this week and 47h in TIMELOG.md history
    When the user runs "gittan status"
    Then the status table shows "3h" under "This period" for Project Alpha
    And shows "47h" under "Total observed" for Project Alpha

  Scenario: Project with no TIMELOG.md history
    Given Project Beta has IDE events this week but no TIMELOG.md entries
    When the user runs "gittan status"
    Then "Total observed" shows "—" or "0h" for Project Beta
    And no error is raised

  Scenario: Total observed is read-only and never affects session math
    Given TIMELOG.md has entries for Project Alpha
    When Gittan aggregates the period report
    Then session computation and billable hours are unchanged
    And "Total observed" is a display-only sum, not part of the billing calculation
```

### Acceptance criteria (P1)

- Total observed column appears in `gittan status` output.
- Value is the sum of all TIMELOG.md-sourced hours for the project, no date
  filter applied.
- Projects with no TIMELOG.md history show `—` or `0h`; no crash or warning.
- Period hours, session math, and billable total are unaffected.
- Terminal output follows style guide: muted value color, aligned columns.
- Full autotest suite green (`bash scripts/run_autotests.sh`).
- No Python file exceeds 500 lines.

### Validation (P1)

| Scenario | Evidence |
|---|---|
| Total observed beside period hours | Unit test with TIMELOG fixture spanning multiple months |
| Zero-history project shows `—` | Unit test with project having no TIMELOG entries |
| Session math unchanged | Existing session tests still pass; no delta in golden eval |
| Terminal output | `cli_impact_smoke.sh` + manual review of column alignment |

---

## P2 — Git-only column (opt-in via `--git`)

### Task

Add a new `collectors/git_commits.py` that reads `git log` for repos configured
in `timelog_projects.json` and produces events with `source="git"`. Wire it into
`gittan status --git` as a new optional column.

### Configuration

Add an optional `git_repo` field to project profiles in `timelog_projects.json`:

```json
{
  "name": "Project Alpha",
  "match_terms": ["alpha", "owner/project-alpha"],
  "git_repo": "~/code/project-alpha"
}
```

Multiple repos per project are supported as a list:
`"git_repo": ["~/code/frontend", "~/code/backend"]`

### Collector behavior

- Reads `git log --author=<user> --format="%ai"` for each configured `git_repo`.
- Groups commit timestamps into sessions using the same gap logic as
  `compute_sessions()` with `min_session_passive` floor (not the AI-source floor).
- Uses `core/repo_slug.py` to resolve repo path → `owner/repo` slug for
  attribution confirmation.
- When a period already has stronger signals (IDE/AI events) for the same
  project+time range, git-commit sessions are **suppressed** to avoid double-
  counting (dedup against existing sessions by overlap, not addition).
- Registered in `core/collector_registry.py` with `enabled=False` by default;
  activated only when `--git` flag is passed.
- Git author identity resolved from `git config user.email` of each repo.

### Non-goals (P2)

- Not a replacement for AI/IDE signals — explicitly a comparison column.
- No inference of hours from commit message content or diff size.
- No network calls; local `git log` only.
- Not shown in `gittan report` (status only, for now).

## Behavior Contract (P2)

```gherkin
Feature: Git-only column in gittan status
  Users with configured git repos see a transparent git-derived time estimate
  alongside Gittan's activity-based numbers, as a comparison and bootstrap signal.

  Background:
    Given timelog_projects.json has Project Alpha with git_repo pointing to a local clone
    And the clone has commits from the user across multiple weeks

  Scenario: Git-only column appears with --git flag
    Given Project Alpha has 5h from IDE events this week
    And git log shows commits spanning 3h of inferred sessions this week
    When the user runs "gittan status --git"
    Then the status table shows "5h" under "This period"
    And shows "3h" under "Git only" for Project Alpha
    And the column is labeled to indicate it is a git-derived estimate

  Scenario: Git-only not shown without flag
    When the user runs "gittan status" without --git
    Then no "Git only" column appears
    And no git log subprocess is run

  Scenario: No git_repo configured for project
    Given Project Beta has no git_repo in timelog_projects.json
    When the user runs "gittan status --git"
    Then Project Beta shows "—" in the Git only column
    And a note in --source-summary indicates which projects lack git config

  Scenario: Git-only does not inflate hours when IDE events overlap
    Given Project Alpha has IDE events 10:00–12:00 on a given day
    And git commits exist in the same 10:00–12:00 window
    When Gittan aggregates with --git
    Then the git sessions are suppressed for that overlap window
    And total hours for that day are not double-counted

  Scenario: New user with no TIMELOG.md but git history
    Given no TIMELOG.md entries exist
    And git_repo is configured with 6 months of commits
    When the user runs "gittan status --git"
    Then "Git only" shows a non-zero estimate from historical commits
    And the column is clearly labeled as a git-only estimate (not Gittan-verified)
```

### Acceptance criteria (P2)

- `collectors/git_commits.py` registered as `enabled=False` in collector registry.
- `--git` flag activates the collector and adds the Git only column to status.
- Git sessions use `min_session_passive` floor.
- Overlap dedup: git sessions that fall within existing project+day sessions are
  not added to the total.
- `--source-summary` shows the git collector and which repos were read.
- Doctor (`gittan doctor`) warns if `git_repo` path does not exist.
- No Python file exceeds 500 lines.
- Full autotest suite green.

### Validation (P2)

| Scenario | Evidence |
|---|---|
| Git sessions computed from fixture log | Unit test with deterministic `git log` fixture |
| Overlap suppression | Unit test: IDE event + overlapping git commit → no double-count |
| --git flag gates collector | Integration test: collector not called without flag |
| No git_repo → `—` in column | Unit test with project missing git_repo field |
| source-summary shows git collector | `cli_impact_smoke.sh` with --git --source-summary |

---

## Implementation order

1. P1 (Total observed) — standalone, no new collector, lower risk.
2. P2 (Git-only collector) — builds on P1 table layout; reuses `repo_slug.py`.

## Branch

`task/repo-time-totals` from latest `main`.

## Traceability

- story_id: GH-146
- spec_status: draft
- implementation_status: shipped
- created_at: 2026-06-12
- last_updated_at: 2026-06-12
- implementation.pr: pending
- implementation.branch: task/repo-time-totals
- implementation.commits: []
- validation.evidence: pending
- validation.decision: GO — P1 + P2 merged in PR #147
- changelog:
  - 2026-06-12: Initial draft. Feature shaped from beta tester request and product-owner planning session. Prerequisite PR #144 (repo_slug.py) confirmed merged.
