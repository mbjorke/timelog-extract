# Timelog Health Monitor

Status: draft spec  
Last updated: 2026-05-29

## Purpose

Make it obvious whether Gittan's maintained worklog capture is alive today.

The original repo-local `TIMELOG.md` model was easy to notice because a file in
the repository changed. The maintained model uses central per-project worklogs
under Gittan home, which is cleaner for reporting but less visible during the
day. Users need a health surface before they can trust the invisible pipeline.

## Product Goal

Give the user a small, always-available confidence signal:

- How many hours has Gittan observed/classified today?
- Is commit-to-worklog capture still appending to central worklogs?
- Which projects have fresh entries today?
- Are any configured worklog files missing, stale, or unreadable?
- Is local shadow evidence retention active and recently capturing?

The dream UX is a macOS menu bar number near the clock showing today's worked
hours, with a click target for source health.

## Scope

In scope for the first pass:

- CLI/JSON health command or status section.
- Central per-project worklog freshness checks.
- Shadow evidence freshness checks once `local-evidence-shadow-log` exists.
- Today's observed/classified hours summary.
- Machine-readable state for later menu bar or widget surfaces.

Out of scope for the first pass:

- Building the macOS menu bar app itself.
- Posting notifications by default.
- Treating today's live number as invoice truth.
- Reading repo-local `TIMELOG.md` as proof of maintained capture health.

## Behavior Contract

```gherkin
Feature: Timelog health monitor
  Users can tell whether central worklog capture is working today.

  Scenario: Healthy central worklog capture
    Given a project profile has a configured worklog under Gittan home
    And that worklog has an entry from today
    When the user checks timelog health
    Then the project should be marked "fresh"
    And the output should include today's observed or classified hours

  Scenario: Stale central worklog capture
    Given a project profile has a configured worklog under Gittan home
    And that worklog has no entry from today
    When the user checks timelog health
    Then the project should be marked "stale"
    And the output should suggest checking global timelog setup

  Scenario: Missing configured worklog
    Given a project profile points to a missing worklog file
    When the user checks timelog health
    Then the project should be marked "missing"
    And the command should not create or move any worklog file

  Scenario: Menu bar source uses machine-readable health
    Given the health command can output JSON
    When a macOS menu bar companion reads the JSON
    Then it can display today's hours
    And it can show stale or missing capture state without parsing prose output

  Scenario: Shadow evidence retention is stale
    Given local shadow logging is enabled
    And no shadow evidence has been captured today
    When the user checks timelog health
    Then the shadow log should be marked "stale"
    And the output should distinguish retention health from worklog freshness
```

## Health States

| State | Meaning |
| --- | --- |
| `fresh` | Configured worklog exists and has at least one entry in the expected freshness window. |
| `quiet` | Configured worklog exists, but no entry is expected yet based on current activity/window. |
| `stale` | Configured worklog exists, but expected recent entries are missing. |
| `missing` | Configured worklog path does not exist. |
| `unreadable` | Configured worklog path exists but cannot be read. |
| `unconfigured` | Project has no explicit worklog path. |

The same state vocabulary can be reused for shadow-log retention, but the output
must label whether a state describes worklog capture or evidence retention.

## Suggested CLI Shape

Names are intentionally provisional:

- `gittan health`
- `gittan health --today`
- `gittan health --format json`
- `gittan status --health`

The active command should reuse existing report/status internals where possible
but keep health output terse and stable.

## Suggested JSON Shape

```json
{
  "schema": "gittan.timelog_health",
  "date": "2026-05-29",
  "today": {
    "observed_hours": 4.25,
    "classified_hours": 3.75
  },
  "worklogs": [
    {
      "project": "project-alpha",
      "path": "~/.gittan/worklogs/project-alpha.md",
      "state": "fresh",
      "last_entry_at": "2026-05-29T14:10:00+03:00",
      "entries_today": 3
    }
  ],
  "shadow_log": {
    "state": "fresh",
    "last_capture_at": "2026-05-29T14:12:00+03:00",
    "records_today": 42
  }
}
```

## Menu Bar Direction

A future macOS menu bar surface should consume JSON rather than reimplementing
Gittan logic. It should show:

- today's classified hours as the compact number,
- warning state when capture is stale/missing,
- a click-through detail list by project/source,
- no raw activity details in the menu bar by default.

## Open Questions

- Should freshness be based only on worklog entries, or correlated with Git
  commits / active report evidence?
- What is the default stale threshold during a workday: no entry today, no entry
  in N hours, or no entry after a commit?
- Should the menu bar show observed hours, classified hours, or both?
- Should health become part of `gittan doctor`, `gittan status`, or a separate
  command?
- Should shadow-log freshness be required before the menu bar shows a green
  health state?
