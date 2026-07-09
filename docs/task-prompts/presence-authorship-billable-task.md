# Task Prompt: Presence ≠ authorship for default billable (cache-mtime / brackets)

## Traceability

- story_id: `GH-327`
- spec_status: `approved`
- implementation_status: `in progress`
- created_at: `2026-07-09`
- last_updated_at: `2026-07-09`
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/341
- implementation.branch: `task/presence-authorship-billable-327`
- implementation.commits: `[d6c9a09]`
- validation.evidence: `tests/test_attendance_classification.py` (TestBillableExcludesPresence); `tests/test_presence_bracketing.py`
- validation.decision: `conditional GO`
- changelog:
  - `2026-07-09: Decision — option 1 (presence-only tier). Attended for reporting; not default-billable.`
  - `2026-07-09: Slice 1 started — taxonomy + billable gate + labeled surface.`
  - `2026-07-09: Slice 1 PR #341 — PRESENCE_SIGNAL_SOURCES (Lovable + comparators); Chrome/WP deferred to Slice 2.`

## Decision (PO, 2026-07-09)

**Option 1 — presence-only tier.** Sources whose evidence is a *presence*
signal (cache-mtime, browser history, Screen Time / Timely Memory brackets)
stay **attended** on the GH-284 attendance axis (honest reporting) but are
**not default-billable**. They require the same explicit opt-in / confirm path
as autonomous agent hours before they enter the billable total.

This resolves the tension left by #313/#324: Lovable (desktop) is correctly
`ATTENDED` for the report, yet its evidence role remains `PASSIVE_CONTEXT`
(cache-mtime ≠ active authorship). Bracketed minutes from GH-332 inherit the
same gate.

## Problem

Two orthogonal axes were collapsed into one billable default:

| Axis | Meaning | Examples |
| --- | --- | --- |
| Attendance (GH-284) | Was the operator present / interacting? | Cursor, Lovable, Chrome vs Claude Code CLI loops |
| Billable signal (this issue) | Is the evidence *authorship* or mere *presence*? | Cursor prompts vs Lovable cache-mtime / edge brackets |

Without the second axis, presence-signal hours flow into default-billable
whenever attendance is `attended` — generous until reported-time confirm (#263)
is adopted.

## Behavior (target)

```gherkin
Feature: Presence-signal hours are confirm-gated for billing
  Attended reporting stays honest; default billable requires authorship
  (or an explicit opt-in).

  Scenario: Pure presence session is attended but not default-billable
    Given a session whose events are only presence-signal sources
      (e.g. Lovable desktop cache-mtime)
    When the report is generated
    Then the session is labeled attended
    And its hours appear under presence_hours
    And default billable excludes those hours

  Scenario: Authorship session stays default-billable
    Given a session with Cursor (or other authorship) evidence
    When billable totals are computed
    Then those hours remain in the default billable set
    And mixed authorship+presence sessions stay billable (authorship present)

  Scenario: Bracketed edge minutes are presence-gated
    Given --presence-bracket on extended a session into Timely Memory
    When billable totals are computed
    Then bracketed_hours are excluded from default billable
    And they remain visible as labeled observed time

  Scenario: Opt-in restores presence to billable
    Given --include-presence-billable
    When billable totals are computed
    Then presence_hours (incl. brackets) are counted like attended authorship
```

## Slices

### Slice 1 — taxonomy + billable gate + surface (priority: now)

- Add `PRESENCE_SIGNAL_SOURCES` (and helper) in `core/sources.py`; document the
  axis next to `ATTENDED_SOURCES` / evidence roles. Slice 1 set: Lovable
  (desktop/web) + Screen Time / Timely Memory. Chrome/WordPress/Mail stay
  default-billable until Slice 2 weighted split.
- Track `presence_hours` on day payloads (overall + project reports) for
  sessions whose sources are *all* presence-signal.
- After presence bracketing, attribute `bracketed_hours` into project
  `presence_hours` (proportional share) so the billable path sees them.
- `project_billable_raw_hours` excludes `presence_hours` by default; CLI flag
  `--include-presence-billable` (mirrors `--include-agent-billable`).
- Terminal Review summary + PDF note + truth payload expose the split.
- Update `docs/task-prompts/attended-agent-time-task.md` with a pointer to this
  axis; keep Lovable as attended.

### Slice 2 — weighted split inside mixed sessions (priority: next)

- When a session mixes authorship + presence sources, allocate only the
  presence-weighted share into `presence_hours` (reuse `project_hours` weights).
- Optional: confirm-gate UX copy in Project-hour review.

### Slice 3 — reported-time confirm adoption (priority: later)

- Once #263 Phase 4 is the normal path, presence-gated hours become a soft
  reminder rather than the primary guard; keep the taxonomy.

## Non-goals

- Reclassifying Lovable back to `agent` (GH-313 decision stands).
- Changing observed / attended totals — only the *billable default* changes.
- Inventing project time from Screen Time / Timely Memory alone (GH-332).
- Keystroke-level authorship detection.

## Dependencies

- #284 / #313 — attendance axis (built).
- #332 — bracketing produces `bracketed_hours` that this gate must cover.
- #263 — longer-term confirm layer; this issue is the pre-adoption guard.
