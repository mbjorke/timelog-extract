# Scheduled → Reported time bridge

Status: draft spec  
Last updated: 2026-06-01 (role-per-calendar + Pierre persona)

## Purpose

Define one shared target for **reported time** — a confirmed, optionally edited
duration for a unit of work — so that Calendar, Toggl, and Jira stop being three
separate paths with no common destination.

Today:

- Calendar's role **depends on the calendar** (see *Calendar role per
  calendar*): a dedicated time-report calendar is a `primary_claim`, while a
  meetings calendar is `scheduled_context` that should not silently become worked
  time.
- Toggl is `primary_claim`: externally tracked time entries.
- `jira-sync` already turns derived session time into Jira worklogs with a
  confirm/dry-run loop.

Motivating user: [`../product/persona-pierre-calendar-timereport.md`](../product/persona-pierre-calendar-timereport.md)
keeps a dedicated `TimeReport` calendar where every event is a deliberate time
entry — proof that a calendar source cannot assume a single role.

Each writes (or would write) to its own place. This spec introduces a single
structured `reported_time` record that all three map into, so a confirmed
meeting, a Toggl entry, and a Jira-bound session use the same contract.

This spec is **design only**. It does not add code or a collector. It is the
root dependency for the Calendar collector and its reconcile/edit flow (see
*Delivery phases*).

## Non-goals

- No collector implementation (Calendar MVP is downstream — see
  [`source-collector-contract.md`](source-collector-contract.md)).
- No invoice approval. `reported_time` is **not** approved invoice time; approval
  remains a separate, later layer.
- No automatic promotion of scheduled context into reported time without explicit
  user confirmation.
- No new external API integrations beyond what Toggl/Jira already do.

## Where it sits in the evidence layers

[`source-evidence-policy.md`](source-evidence-policy.md) defines three layers.
This spec inserts a fourth, **between classified and approved**:

| Layer | Meaning | Who sets it |
| --- | --- | --- |
| Observed time | Activity inferred from source events. | Collectors. |
| Classified time | Observed time mapped to project/customer. | `classify_project`. |
| **Reported time** | A confirmed (optionally edited) duration intended for external reporting. | **User confirmation / edit, or an external primary claim.** |
| Approved invoice time | Human-approved billable time. | Invoice approval (out of scope here). |

A source producing `scheduled_context` (Calendar) may **propose** reported time
but never set it without confirmation. A `primary_claim` source (Toggl) maps to
reported time directly, with provenance preserved.

## The `reported_time` record

A reported-time record is the shared structure every path writes and every
consumer (Toggl/Jira sync, report surfaces) reads.

Proposed fields (names provisional):

| Field | Meaning |
| --- | --- |
| `id` | Stable id / deterministic fingerprint for the reported unit. |
| `date` | Local date the time is reported against. |
| `project` | Classified project/customer. |
| `hours` | Confirmed duration (the edited value wins over any observed value). |
| `source` | Origin: `calendar`, `toggl`, `session` (derived work), … |
| `origin_ref` | Provenance back to the source event(s): calendar event id, Toggl entry id, session fingerprint. |
| `state` | `proposed` \| `confirmed` \| `edited` \| `dismissed`. |
| `edited_from_hours` | Original value when `state = edited` (audit trail). |
| `note` | Optional human note (e.g. "meeting billed at agreed rate"). |
| `captured_at` / `confirmed_at` | Timestamps for capture and confirmation. |

Rules:

- `hours` is authoritative for reporting; `edited_from_hours` keeps the original
  for audit when a user changes it.
- `origin_ref` must always point back to real evidence — no orphan reported time.
- A record stays `proposed` until the user confirms; `proposed` records are shown
  but never sent to Toggl/Jira or counted as reported totals.

## Calendar role per calendar

A calendar source must not assume one role for all calendars. The user selects
which calendars to read and assigns a **role per calendar** (across Google,
iCloud, and multiple org accounts — all readable from the local
`Calendar.sqlitedb` when subscribed):

| Calendar kind | Role | Behavior |
| --- | --- | --- |
| Dedicated time-report (e.g. `TimeReport`) | `primary_claim` | Each event is a user-authored claim → maps to reported time as `confirmed`, provenance preserved. |
| Meetings / `Work` | `scheduled_context` | Proposes reported time → `proposed`, requires confirmation, never silent. |
| Personal / family / holidays | (not collected) | Excluded; not read. |

Config shape (provisional): a list of `{ calendar, account, role }` rather than a
single hardcoded name. Default with no config is conservative: read nothing until
the user opts a calendar in.

For a `primary_claim` calendar, the user's entered hours are **authoritative**.
Corroboration from work evidence (see persona Tier 3) is a confidence annotation,
**never** an override — consistent with
[`source-evidence-policy.md`](source-evidence-policy.md) ("no source silently
overrides").

## How each source maps in

| Source | Role | Maps to reported time when… | Default state |
| --- | --- | --- | --- |
| Calendar — time-report calendar | `primary_claim` | events are read from a calendar the user marked as a time-report. | `confirmed` (preserve provenance) |
| Calendar — meetings calendar | `scheduled_context` | the user confirms a meeting (optionally editing hours) in reconcile. | `proposed` |
| Toggl | `primary_claim` | an entry is imported with explicit project mapping. | `confirmed` (preserve provenance) |
| Derived work sessions | `direct_work_evidence` | promoted via the existing `jira-sync`-style confirm loop. | `proposed` |

No source bypasses confirmation to reach `confirmed` except an external
`primary_claim` the user already authored (a time-report calendar, Toggl).

## Reconcile contract (overlap handling)

When a `proposed` meeting overlaps `direct_work_evidence` in the same window, the
user must choose — mirroring the existing `jira-sync` candidate loop
([`../runbooks/jira-worklog-sync.md`](../runbooks/jira-worklog-sync.md)):

- candidates are listed,
- nothing is written under `--dry-run`,
- each candidate is confirmable (interactive or `--require-confirm`),
- the chosen/edited duration becomes a `reported_time` record,
- automation (`--yes`) must skip ambiguous overlaps with a clear reason rather
  than guessing.

## Behavior Contract

```gherkin
Feature: Scheduled to reported time bridge
  Confirmed durations from any source land in one shared reported-time record.

  Background:
    Given the reported-time bridge is available

  Scenario: A dedicated time-report calendar maps in as a primary claim
    Given a calendar the user marked as a time-report calendar
    And it has an event "KidneySign" from 09:00 to 12:00
    When the events are read
    Then a reported_time record should be created with state "confirmed"
    And hours should be 3.0
    And its origin_ref should preserve the calendar event id

  Scenario: A meeting calendar only proposes until confirmed
    Given a calendar the user marked as a meetings calendar
    And a meeting overlaps direct work evidence in the same window
    When a report is produced without confirmation
    Then the meeting should be state "proposed"
    And it should not be counted as reported time until the user confirms it

  Scenario: A confirmed meeting becomes a reported-time record
    Given a calendar meeting overlaps direct work evidence in the same window
    When the user confirms or edits the time in reconcile
    Then a reported_time record should be written
    And its origin_ref should point back to the calendar event
    And Toggl/Jira sync should read the same record without source-specific logic

  Scenario: Corroboration annotates a primary claim without overriding it
    Given a time-report entry of 3.0 hours for "KidneySign"
    And work evidence shows 2.4 hours of activity in the same window
    When the report is produced
    Then the reported hours should stay 3.0
    And the entry may show a corroboration annotation
    But the entered hours should not be overridden

  Scenario: An edited duration keeps an audit trail
    Given a proposed reported-time record of 2.0 hours
    When the user edits it to 1.5 hours
    Then hours should be 1.5
    And edited_from_hours should be 2.0
    And state should be "edited"

  Scenario: Scheduled context never becomes reported time silently
    Given a calendar meeting with no user confirmation
    When a report is produced
    Then the meeting may appear as proposed or supporting context
    But it should not be counted as reported time
    And it should not be sent to Toggl or Jira

  Scenario: Toggl entries map in as primary claim with provenance
    Given a Toggl time entry with an explicit project mapping
    When it is imported into reported time
    Then it should be state "confirmed"
    And its origin_ref should preserve the Toggl entry id

  Scenario: Reported time is not invoice approval
    Given confirmed reported-time records exist
    When the report is shown
    Then reported time should be distinct from approved invoice time
```

## Acceptance Criteria

- Each scenario has automated coverage or a documented manual verification note
  when implementation begins.
- The record schema lists required vs optional fields and their states.
- A mapping table shows Calendar / Toggl / derived sessions → `reported_time`.
- Storage location is decided before the first writer ships (see Open questions).
- Privacy: meeting titles and notes follow
  [`source-evidence-policy.md`](source-evidence-policy.md) redaction rules in any
  JSON/terminal output.

## Delivery phases

This spec is phase 0 (design). Downstream work, each its own task:

1. **Bridge spec (this doc).** Root dependency.
2. **Calendar collector MVP** — `scheduled_context`, Meetings column, all-day
   excluded, recurring = documented v1 limit; proposes (never sets) reported
   time. Built via the `gittan-source-collector` skill.
3. **Reconcile + edit** — overlap loop writes `reported_time`.
4. **Toggl/Jira posting from `reported_time`** — Calendar-confirmed time can post
   through existing sync; Calendar becomes a `primary_claim` contributor.

## Open questions

- **Storage:** a new structured store (e.g. `$GITTAN_HOME/reported/…`) vs extending
  per-project worklogs vs a field in the truth payload? The maintainer's
  direction is a **new structured field/schema**; confirm the on-disk shape and
  whether it is per-project or global before phase 3.
- Should `reported_time` records be emitted in the truth payload (and at which
  version) so external callers can read them?
- Should reconcile group by `project + day` (like `jira-sync` worklogs) or keep
  per-event granularity?
- How long are `proposed`/`dismissed` records retained, and does the shadow log
  ([`local-evidence-shadow-log.md`](local-evidence-shadow-log.md)) hold their
  provenance?
- Should Toggl import auto-confirm, or also pass through reconcile when it
  overlaps derived sessions?
