# Source Evidence Policy

Status: draft policy  
Last updated: 2026-05-29

## Purpose

Define how Gittan should interpret different data sources. A source can be good
evidence for context without being strong evidence for worked time or invoice
approval.

This policy prevents new integrations from treating all events as equal just
because they share the same internal event shape.

Retention is a separate concern: a source can be high-value evidence and still
be fragile if its original logs rotate or get deleted. Durable local retention is
covered by `docs/specs/local-evidence-shadow-log.md`.

## Core Principle

Sources produce evidence, not truth by themselves.

Gittan output should keep these layers separate:

- **Observed time**: activity inferred from source events.
- **Classified time**: observed time mapped to project/customer.
- **Approved invoice time**: human-approved billable time.

No source should silently promote classified time into approved invoice time.

## Evidence Roles

| Role | Meaning | Examples |
| --- | --- | --- |
| `primary_claim` | User-authored or externally tracked claim about work performed. | configured per-project worklogs, Toggl time entries. |
| `direct_work_evidence` | Strong signal that work happened in a tool or repository. | Cursor, Codex IDE, AI CLI logs, commits/PRs when available. |
| `delivery_evidence` | Evidence of shipped or reviewed work, but not always duration. | GitHub events, Jira worklog sync candidates. |
| `passive_context` | Ambient activity that helps explain or classify time. | Chrome history, Apple Mail. |
| `scheduled_context` | Planned meeting or focus block; useful context, weak duration proof by itself. | Calendar events. |
| `coverage_comparator` | Reference total or gap signal, not an ordinary event source. | Screen Time. |

## Initial Source Matrix

| Source | Role | Can create sessions? | Can classify sessions? | Can override direct work evidence? | Notes |
| --- | --- | --- | --- | --- | --- |
| Configured per-project worklogs | `primary_claim` | yes | yes | yes, when source strategy says worklog-first | Maintained reporting should use explicit project `worklog` paths under Gittan home. Repo-local `TIMELOG.md` is legacy fallback only. |
| Toggl | `primary_claim` | yes | yes | no by default | External tracked-time claim; preserve provenance and keep separate from invoice approval. |
| Cursor / Codex / AI CLI logs / Zed | `direct_work_evidence` | yes | yes | usually yes over passive sources | High value for actual work activity. |
| GitHub | `delivery_evidence` | yes, cautiously | yes | no by itself | Strong project anchor, weak duration signal unless correlated with other activity. |
| Chrome / Lovable desktop history | `passive_context` | yes, cautiously | yes | no | Good for context and project hints; noisy for duration. |
| Apple Mail | `passive_context` | yes, cautiously | yes | no | Communication context; permission-sensitive. |
| Calendar | `scheduled_context` | no by default | yes, as support | no | Meeting context can support classification but should not inflate work alone. |
| Screen Time | `coverage_comparator` | no | no | no | Use for gap analysis and coverage warnings, not as normal event evidence. |

## Weighting Guidance

Implementation may use numeric scores later, but the policy should stay readable
without a specific formula:

- Direct work evidence beats passive context.
- User-authored worklog claims can be primary when source strategy selects them.
- Worklog health matters: a primary claim source that has stopped receiving
  entries should be surfaced as stale, not silently trusted.
- Evidence retention matters: source weighting should not assume upstream logs
  remain available after the day ends.
- Calendar events support classification and explanation, but do not prove work
  duration alone.
- Delivery evidence is good for project attribution and shipped-work narrative,
  but should not create large sessions without nearby activity evidence.
- Coverage comparators should flag gaps; they should not manufacture project
  time.

## Calendar Policy

Calendar integrations should follow these rules unless a later spec overrides
them:

- Calendar is opt-in or explicit-auto with clear permission diagnostics.
- Calendar events are supporting context by default.
- All-day events must not create full-day work sessions.
- Recurring events must be expanded only within the requested report window.
- Private/redacted event fields must remain safe in JSON and terminal output.
- Calendar title, location, URL, attendees, and notes are potential project
  hints, but direct work evidence remains primary when sources disagree.

## Behavior Contract Sketch

```gherkin
Feature: Source evidence roles
  Sources contribute different kinds of evidence to a report.

  Scenario: Calendar supports classification without creating work alone
    Given the Calendar source is enabled
    And a calendar event titled "Project Alpha planning" exists from 09:00 to 10:00
    And no direct work evidence exists during that window
    When Gittan builds the report
    Then the calendar event may appear as supporting evidence
    But it should not create a high-confidence worked-time session by itself

  Scenario: Direct work evidence beats passive context
    Given Cursor activity points to "Project Alpha"
    And Chrome history in the same window points to a generic website
    When Gittan classifies the session
    Then the direct work evidence should carry more weight than the passive context
```

## Open Questions

- Should source weights be user-configurable, or versioned only as policy?
- Should Toggl be treated as a primary claim only when workspace/project mapping
  is explicit?
- Should source roles be emitted in the truth payload before numeric confidence
  scoring is fully implemented?
- Should calendar events be hidden from terminal output by default when marked
  private by the provider?
