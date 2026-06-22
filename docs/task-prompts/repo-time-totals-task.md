# Per-project totals in `gittan status`: historical columns (TIMELOG + Git)

> **Status update (2026-06-22, product-owner pass):** Maintainer intent clarified:
> the valuable **bootstrap / all-time** signal is **Git observed** (commit-derived),
> not a vague "total observed." **TIMELOG observed** (worklog all-time) is a
> separate, optional corroboration column for users with global hook + worklog
> discipline. Ship historical columns **behind `--history`** so default
> `gittan status` stays a single period `Hours` column. Accuracy net (sanity
> bounds + golden eval composer fixture) is ✅ — safe to reintroduce historical
> columns once labeled correctly. See *Historical columns (revised plan)* below.

> **Status update (2026-06-15):** Beta testing surfaced a catastrophic accuracy
> regression in the period `Hours` column (composer day-collapse). The withdrawn
> **Total observed** column was TIMELOG all-time but **misread** as "everything
> Gittan saw." It was removed until the accuracy net landed (now complete).

## Problem

`gittan status` and `gittan report` show hours for the **selected period only**.
There is no quick way to see **historical magnitude** per project, or to bootstrap
an estimate from local git history for new users who have not yet built up IDE/AI
telemetry.

Two **distinct** historical signals were conflated under "Total observed":

1. **TIMELOG observed** — sum of all `TIMELOG.md` entries per project (all-time).
   Answers: *"How much have I **logged** about this project?"* Best when global
   timelog hooks feed per-repo worklogs (`docs/runbooks/global-timelog-setup.md`).

2. **Git observed** — session estimate from `git log` timestamps on configured
   `git_repo` paths. Answers: *"How much does **commit activity** suggest?"* Best
   for onboarding (months of commits, sparse worklog) and Lovable/Claude Code
   auto-commit workflows.

**Out of scope for this story:** Total Invoiced (requires new billing log storage).

## Historical columns (revised plan)

### Three period vs history concepts

| Column (UX label) | Question it answers | Source | Time window | Default visible |
|---|---|---|---|---|
| **Hours** | How much this period? | All enabled collectors | Selected period | Yes |
| **Git observed** | Commit-derived estimate? | `git log` on `git_repo` | **All-time** (primary); optional period slice later | No — `--history` |
| **TIMELOG observed** | How much logged in worklog? | `TIMELOG.md` only | All-time | No — `--history` |

**Not comparable:** period `Hours` (multi-source) vs either historical column.
Historical columns are also not comparable with each other — TIMELOG = recorded
work; Git = commit proxy. Showing both is **corroboration light** (alignment /
gaps), not a merged truth.

### Recommended rollout (product-owner)

1. **`--history` first** — opt-in flag on `gittan status` (and later `report`)
   that adds historical sub-columns without widening the default table.
2. **Git observed (all-time) first** — matches maintainer intent; reuses
   `core/git_totals.py` with no `dt_from`/`dt_to` (already supported). Rename
   terminal header from "Git only" → **"Git (all-time)"** or **"Git estimate"**.
3. **TIMELOG observed optional second** — restore `compute_timelog_project_totals`
   under `--history` only; label **"TIMELOG (all-time)"**, never "Total observed".
4. **Show a column only when data exists** — `—` when no `git_repo` / no worklog
   rows; do not run `git log` unless `--history` or legacy `--git` (deprecate
   `--git` toward `--history` in a follow-up).
5. **Both columns display-only** — never affect period session math, billable
   totals, or truth-payload hours.

### When you need one vs both

| Your workflow | Start with |
|---|---|
| Commits often, worklog sparse | Git observed only |
| Global hook + reliable `TIMELOG.md` | TIMELOG observed; add Git for cross-check |
| Both established | Both under `--history` when comparing log vs commit rhythm |

### Decision test (for operators)

After `gittan status --last-month`:

1. *"Do period hours look sane?"* → **Hours** + sanity bounds / presence-estimated.
2. *"How much have I ever touched this repo?"* → **Git observed (all-time)** if
   `git_repo` is configured.
3. *"How much is written in the worklog total?"* → **TIMELOG observed** if hooks
   or manual logging are trusted.
4. *"Do I log and commit in step?"* → **both** historical columns; interpret the
   gap, do not sum them.

## Prerequisite

[PR #144](https://github.com/mbjorke/timelog-extract/pull/144) (merged) —
`core/repo_slug.py` provides cached path→`owner/repo` slug resolution that the
git-only collector reuses for project attribution.

## Proposed columns in `gittan status`

| Column (label) | Source | Shown when |
|---|---|---|
| Hours (period) | Existing report engine | Always |
| Git observed | `git log` all-time on `git_repo` | `--history` (recommended); today `--git` shows **period** git only — migrate |
| TIMELOG observed | `TIMELOG.md` all-time sum | `--history` only |

**Deprecated naming:** do not ship **"Total observed"** — it implied "everything
Gittan saw." Use explicit source labels in the terminal header and a one-line
legend under the table when `--history` is on.

**Semantics note:** period `Hours` aggregates **all sources** for the window.
TIMELOG observed and Git observed are **independent historical estimates**;
a sparse worklog reads lower than commit-heavy months — that is expected, not a
bug.

## Critical dependency: session integrity

The period `Hours` column is only trustworthy if session computation is sound.
Beta testing proved it was not: `collectors/cursor_composer.py` laid a 14-minute
heartbeat grid across each composer thread's entire `createdAt → lastUpdatedAt`
span. Long-lived threads (days–weeks) fabricated continuous activity around the
clock, so the 15-minute session gap never closed and whole days merged into single
~24h sessions. 27 of 30 days collapsed; akturo read 293.8h for one month.

Fixed by switching to **bounded bursts anchored on real touches** (createdAt,
lastUpdatedAt, checkpoints, branch interactions); idle gaps are no longer filled.
After the fix the same month reads 108.9h with zero day-collapse.

**This class of bug had no test coverage and two tests actively froze the buggy
behavior as expected.** Re-introducing the Total observed column is gated on the
following sibling backlog items (product-owner pass, 2026-06-15):

1. **Accuracy sanity-bound guardrails** — ✅ **LANDED (2026-06-15).**
   `core/sanity_bounds.py` flags sessions > 16h, days attributing > 24h, and
   observed-vs-Screen-Time over-attribution > 1.5×; warnings render under the
   Review summary (`outputs/terminal.py`). Covered by `tests/test_sanity_bounds.py`.
2. **Golden eval covers high-frequency telemetry** — ✅ **LANDED (2026-06-16).**
   `tests/fixtures/golden_cursor_composer_dataset.json` + `golden_cursor_composer_headers.json`;
   `scripts/run_golden_eval.py` runs all `golden*dataset.json` files with optional
   isolated HOME and invariant checks (`max_hours_any_day`, `max_period_total_hours`).

Accuracy net is complete. Next implementation slice: **`--history` + Git observed
(all-time)**, then optional TIMELOG observed — not both on by default.

## P1 — TIMELOG observed column (optional, `--history` only)

### Task

Restore the dormant **TIMELOG (all-time)** column under `--history` only. Do **not**
use the label "Total observed."

**Current state (2026-06-22):** `core/report_service.py` leaves
`timelog_project_totals` empty; rendering in `outputs/terminal.py` and
`core/timelog_totals.py` remain for re-introduction.

### Key files

- `core/timelog_totals.py` — all-time TIMELOG.md aggregation
- `core/report_service.py` — populate totals when `--history`
- `outputs/terminal.py` — column header **"TIMELOG (all-time)"**
- `core/cli_report_status.py` — add `--history` flag

### Non-goals (P1)

- Do not include IDE/AI events in the total (bounded retention).
- Do not change period hours or billable math.
- Do not show this column without `--history`.

## Behavior Contract (P1)

```gherkin
Feature: TIMELOG observed column in gittan status
  Users who opt in with --history see all-time worklog hours per project.

  Background:
    Given TIMELOG.md contains entries across multiple months for project-alpha
    And the user runs gittan for a one-week period

  Scenario: TIMELOG observed shown only with --history
    Given project-alpha has 3h in this week and 47h in TIMELOG.md history
    When the user runs "gittan status --history"
    Then the status table shows "3h" under "Hours" for project-alpha
    And shows "47h" under "TIMELOG (all-time)" for project-alpha

  Scenario: Default status hides historical columns
    When the user runs "gittan status" without --history
    Then no TIMELOG (all-time) column appears

  Scenario: TIMELOG observed is read-only
    When Gittan aggregates the period report
    Then session computation and billable hours are unchanged
```

### Acceptance criteria (P1)

- Column appears only with `--history`; header **"TIMELOG (all-time)"**.
- Value sums all TIMELOG.md hours for the project; no date filter.
- Projects without worklog history show `—`; no crash.
- Period hours and billable totals unchanged.
- Full autotest suite green.

---

## P2 — Git observed column (`--history`; extends shipped `--git`)

### Shipped today (period scope)

`gittan status --git` adds a **period-scoped** git column via
`compute_git_project_totals(..., dt_from, dt_to)`. Header: "Git only".

### Next slice (product priority)

**Git observed (all-time)** under `--history`:

- Call `compute_git_project_totals` without period bounds (1970–2099).
- Header: **"Git estimate (all-time)"** — commit timestamps, not verified work.
- Still display-only; passive session floor; no overlap inflation of period Hours.

### Task (original collector — built)

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
Feature: Git observed column in gittan status
  Users who opt in see a transparent git-derived estimate alongside period hours.

  Background:
    Given timelog_projects.json has project-alpha with git_repo pointing to a local clone

  Scenario: Git all-time appears with --history
    Given the clone has commits spanning 40h of inferred sessions all-time
    And project-alpha has 5h from IDE events this week
    When the user runs "gittan status --last-week --history"
    Then the status table shows period hours under "Hours"
    And shows the all-time git estimate under "Git estimate (all-time)"
    And the column legend states commit-timestamp derivation

  Scenario: Historical columns hidden by default
    When the user runs "gittan status" without --history
    Then no git all-time column appears
    And no git log subprocess runs unless --git legacy flag is passed

  Scenario: New user with git history but no TIMELOG
    Given no TIMELOG.md entries exist
    And git_repo has six months of commits
    When the user runs "gittan status --history"
    Then Git estimate (all-time) is non-zero
    And TIMELOG (all-time) shows "—"
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

## Implementation order (revised 2026-06-22)

1. **P2b — `--history` + Git observed (all-time)** — primary maintainer intent;
   small delta on shipped P2 (`core/git_totals.py` already supports unbounded range).
2. **P1 — TIMELOG observed under `--history`** — optional corroboration; restore
   `compute_timelog_project_totals` call with new label.
3. **Follow-up — deprecate `--git`** in favor of `--history` (or make `--git` an
   alias that implies period git column only, documented as legacy).

Original order (P1 before P2) is **superseded** — git bootstrap delivers more
value to more users than worklog all-time alone.

## Branch

`task/repo-time-totals` from latest `main`.

## Traceability

- story_id: GH-146
- spec_status: draft (historical columns reframed 2026-06-22)
- implementation_status: P2 period `--git` shipped; P2b `--history` git all-time
  not built; P1 TIMELOG column dormant pending `--history` slice
- created_at: 2026-06-12
- last_updated_at: 2026-06-22
- implementation.pr: #147 (period columns); #154 (golden eval gate); pending for `--history`
- implementation.branch: task/repo-time-totals (historical); new slice TBD
- implementation.commits: []
- validation.evidence: accuracy net + `tests/test_timelog_totals.py`,
  `tests/test_git_totals.py` (if present), golden cursor dataset
- validation.decision: GO for P2b after #154 merges; P1 optional same PR or follow-up
- related:
  - PR #154 golden eval composer guard
  - `docs/runbooks/global-timelog-setup.md` (TIMELOG observed precondition)
- changelog:
  - 2026-06-12: Initial draft.
  - 2026-06-15: Withdrew "Total observed" after composer day-collapse; accuracy net gating.
  - 2026-06-16: Golden eval composer fixture landed (see PR #154).
  - 2026-06-22: Split TIMELOG observed vs Git observed; git-first under `--history`;
    deprecated "Total observed" naming; revised implementation order.
