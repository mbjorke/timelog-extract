# Capture Cursor + show device on the report — close the phone/desktop loop

PR #469 ships the joints: per-device evidence filing and `source_provenance.device`.
What the operator still cannot *see* or *capture* after the walkthrough:

1. **Cursor is not a capture source.** Live Cursor rows already appear in a
   same-machine report, but a Cursor session on another device (or a machine
   whose HOME is only reachable briefly) never enters the durable ledger the way
   `claude-code` / `desktop-code` do via `gittan capture`.
2. **The report never names the device.** Provenance carries `Mac.lan` /
   `iPhone` / a cloud hostname, and doctor Device-coverage shows it — but project
   rows and timeline slugs stay bare (`timelog-extract`), so phone vs desktop
   work is indistinguishable in the narrative the operator actually reads.

This task is the visible half of "a phone is a machine too."

## Traceability

- story_id: `GH-474` (https://github.com/mbjorke/timelog-extract/issues/474)
- spec_status: draft
- implementation_status: not built
- created_at: 2026-07-26
- last_updated_at: 2026-07-26
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-07-26: Drafted from the #469 maintainer walkthrough — capture today is
    Claude-shaped; device is stored but not shown; Cursor asked for next.
    Issued as #474 (`priority:next`).

## Behavior

```gherkin
Feature: Device-aware capture reaches Cursor and the report
  Work on a phone and a Mac is durable and readable as two devices, not one blob.

  Scenario: Cursor sessions can be captured into the ledger
    Given this device holds Cursor session artifacts for today
    When the operator runs gittan capture --source cursor
    Then Cursor events are appended to the evidence ledger
    And each record carries source_provenance.device and captured_via cursor

  Scenario: Capture without --source still includes Cursor with the defaults
    Given Cursor and Claude Code artifacts exist on this device
    When the operator runs gittan capture
    Then both cursor and claude-code contribute when present
    And the run reports which sources contributed

  Scenario: Project rows show which device observed the work
    Given ledger events for project "timelog-extract" from device "Mac"
    And ledger events for the same project from device "iPhone"
    When the operator runs gittan report for that day
    Then the readable project or session labels distinguish Mac from iPhone
    And the underlying project identity used for billing stays "timelog-extract"

  Scenario: A single-device day does not invent noise
    Given all events for a project came from one device
    When the report is rendered
    Then a device suffix may still appear (honesty) or be omitted by a
      documented quiet rule — but never invents a second device
```

## Design notes (decisions still open)

- **Capture:** add `cursor` (and likely `cursor-agent`) to `CAPTURE_SOURCES` by
  wiring existing collectors with a `home` override — same pattern as
  `desktop-code`. Do not invent a second Cursor parser.
- **Labels:** append a short device token to *display* labels only
  (`timelog-extract (Mac)`), not to the project key used for hours / invoice
  grouping. Friendly names (`Mac`, `iPhone`) beat raw hostnames (`Mac.lan`) when
  a small map exists; otherwise show the stored device string.
- **Non-goals:** Claude mobile app (still no local artifact). Changing
  fingerprints so phone and desktop count as two events for the same action.
  Billing a project twice because two devices saw it.

## Acceptance

- `gittan capture --source cursor` is valid and covered by a fixture test.
- Default capture includes the new source key(s) in `CAPTURE_SOURCES`.
- Report / timeline shows a device discriminator on multi-device (and documents
  the single-device rule).
- Invoice / billable project identity is unchanged (no new project buckets from
  device labels).
- Doctor Device-coverage and report stay consistent about which devices exist.

## Dependencies

- #470 / PR #469 merged or at least the capture + provenance machinery on `main`.
- Friendly device-name map is optional v1; raw device string is enough for GO.
