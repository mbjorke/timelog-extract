# Commit events land in the shadow log, not markdown

Make the structured local evidence store (shadow log, GH-151) the primary write
target for commit timestamping. Markdown worklogs under
`~/.gittan/worklogs/<project-id>.md` become a generated/optional **view**, not
the data layer.

## Background / incident

On 2026-07-20 a session traced why central worklog capture had silently stopped
on 2026-06-25 (~3 weeks of missing worklog evidence). Root causes:

1. The global post-commit hook derived worklog filenames from a **path hash**
   (`<repo>-<sha1-8>.md`), diverging from the documented `<project_id>.md`
   standard used by config and the migration script. A 2026-07-01 migration was
   finished for exactly one project; 26 empty hash-named files were left behind
   with config pointing at them.
2. The hook only used the central worklog **if the file already existed**,
   silently falling back to the deprecated repo-local `TIMELOG.md`.
3. Nothing surfaced the staleness (`docs/specs/timelog-health-monitor.md` is
   `not started`).

Interim fixes (same session, see implementation refs below): the hook now
resolves the worklog path from `timelog_projects.json` (`project_id` as
identity, aliases supported, no path hash, no pre-existence guard), and a
migration script consolidates the hash-named files.

The structural lesson: commit timestamping writes to a human surface (markdown
files with identity/migration problems) as if it were the data layer, while the
purpose-built structured store (shadow log JSONL, partially built under GH-151)
never receives the signal. This spec closes that gap.

## Ordered backlog

### 1. Commit events land in the shadow log

- priority: now
- problem: the post-commit hook writes only to markdown worklogs; the shadow
  log (append-only JSONL under `~/.gittan/evidence/events/YYYY-MM.jsonl`) is
  built but does not receive commit events. File-surface failures therefore
  lose evidence permanently.
- user value: commit evidence (own wall-clock timestamp, repo, branch, subject)
  survives any worklog file mishap; reports can read commits from the ledger.
- non-goals: no SQLite migration; no removal of markdown worklogs; no cloud
  upload; no change to consent/off-by-default posture of other sources.
- behavior:

```gherkin
Scenario: A commit is recorded as a structured event
  Given the global post-commit hook fires in a scoped repo
  When the commit is recorded
  Then an event with source "git-commit", timestamp, repo, branch and subject
    is appended to the shadow log
  And no markdown worklog write is required for the event to be reportable

Scenario: Markdown worklog becomes a view
  Given commit events exist in the shadow log
  When the user asks for a project worklog file
  Then Gittan can generate or append the markdown from the ledger
  And the ledger remains the source of truth

Scenario: Ledger write failure is not silent
  Given the shadow log directory is missing or unwritable
  When the hook records a commit
  Then the markdown worklog write still happens (transition safety)
  And a diagnostic line is emitted so doctor/status can surface it
```

- acceptance:
  - `gittan report` includes commit events read from the shadow log.
  - Hook markdown write becomes opt-in (kept on during transition).
  - Existing hook resolution (config lookup by `project_id`) is retained.
- validation: fixture test appending a commit event; report run over a fixture
  ledger shows the commit; hook smoke test under `set -euo pipefail`.
- dependencies: GH-151 slice 1 (shadow log foundation, `in progress`).

### 2. Doctor: stale capture warning

- priority: now
- problem: 3 weeks of silent worklog staleness had no surface. Smallest slice
  of `docs/specs/timelog-health-monitor.md`: warn when a configured worklog /
  capture channel has not been written in N days.
- user value: silent evidence gaps become visible in the tool users already
  run (`gittan doctor`).
- non-goals: menu-bar counter; today-hours estimation (later slices of the
  health-monitor spec).
- acceptance: doctor row warns for a configured worklog older than N days
  (default proposed: 7) while fresh worklogs stay quiet; covered by a fixture
  test.
- validation: unit test with aged fixture files; doctor smoke run.
- dependencies: none.

### 3. Finish shadow-log slice 1 (GH-151)

- priority: next
- problem: GH-151 is `in progress` with remaining sub-items; the commit-event
  bridge (item 1) raises the value of finishing them.
- dependencies: none (parallel to item 1).

### 4. Migrate historical markdown worklogs into the ledger

- priority: later
- problem: pre-bridge history lives only in markdown files.
- note: import existing `~/.gittan/worklogs/*.md` entries as ledger events.
  Do not build until item 1 is stable.

### 5. Replace JSONL with SQLite

- priority: do not build yet
- rationale: append-only JSONL meets current volume and query needs; switching
  storage engines before a proven query need would repeat the premature-design
  failure that produced the hash-named worklogs.

## Open decisions

- Duplicate profile identity (two local profiles share one customer; the
  repo-named profile has no worklog, the project-named one holds the history)
  must be resolved before the ledger bridge lands, or one project's commits
  split across two identities. Details in local config, not in this repo.
- Four local profiles lack `project_id`; assign ids before or during item 1.
  (Names live in `timelog_projects.json`, which never enters the repo.)

## Traceability

- story_id: GH-408 (https://github.com/mbjorke/timelog-extract/issues/408)
- spec_status: approved
- implementation_status: built
- created_at: 2026-07-20
- last_updated_at: 2026-07-23
- implementation.pr: pending
- implementation.branch: task/commit-events-to-shadow-log-408
- implementation.commits: []
- validation.evidence: tests/test_global_timelog_hook_script.py, tests/test_doctor_staleness_and_errors.py
- validation.decision: GO
- changelog:
  - 2026-07-20: Initial draft from product-owner pass after the silent
    worklog-capture incident (hook hash-naming + missing-file fallback).
  - 2026-07-23: Implemented git-commit event write, error logging, and staleness doctor checks.
