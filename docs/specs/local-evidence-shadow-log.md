# Local Evidence Shadow Log

Status: draft spec  
Last updated: 2026-05-29

## Purpose

Protect reviewable evidence from source log rotation, browser history cleanup,
app cache resets, and vendor retention limits.

Gittan reads many local traces that are not designed as durable audit records.
If those traces disappear before a report or reconciliation run, the user can
lose evidence for work they actually did. A local shadow log gives Gittan a
controlled, privacy-aware retention layer without introducing a Gittan-operated
cloud service.

## Product Goal

Create a local append-only evidence store that can answer:

- What did Gittan observe at the time, before upstream logs were cleaned?
- Which source produced the evidence?
- Has the retained evidence been tampered with or truncated?
- Can a report be replayed from retained evidence even after source logs rotate?

## Relationship To Existing Specs

- `docs/specs/timelog-truth-standard-rfc.md` already requires frozen input
  snapshots and reproducibility metadata.
- `docs/specs/timelog-health-monitor.md` checks whether today's capture is
  fresh.
- This spec fills the retention gap: capture may be fresh today, but evidence
  can still disappear tomorrow unless Gittan keeps a local shadow copy.

## Non-Goals

- No mandatory upload to Gittan-operated servers.
- No full raw clone of every vendor database by default.
- No hidden background collection without explicit setup/consent.
- No claim that shadow-log evidence is approved invoice truth.

## Retention Model

The shadow log should store normalized evidence records, not unlimited raw
source dumps.

Each record should include:

- stable event id or deterministic fingerprint,
- source name and source-specific provenance,
- observed timestamp and capture timestamp,
- normalized detail text or redacted detail,
- project classification at capture time when available,
- source role from `docs/specs/source-evidence-policy.md`,
- content hash and previous-record hash for tamper-evident chaining.

Raw sensitive fields should be opt-in and redacted by default where practical.

## Storage Direction

Preferred local home:

- `~/.gittan/evidence/`

Possible layout:

- `~/.gittan/evidence/events/YYYY-MM.jsonl`
- `~/.gittan/evidence/manifests/YYYY-MM.json`
- `~/.gittan/evidence/retention-policy.json`

The exact format is open. JSONL is attractive because it is append-friendly,
inspectable, and easy to compact later.

## Behavior Contract

```gherkin
Feature: Local evidence shadow log
  Users keep local evidence even when upstream source logs are rotated or deleted.

  Scenario: New source events are appended to the shadow log
    Given shadow logging is enabled
    And a collector returns a new event for today
    When Gittan records evidence
    Then the event should be appended to the local shadow log
    And the record should include source, observed timestamp, capture timestamp, and fingerprint

  Scenario: Duplicate source events do not create duplicate evidence records
    Given shadow logging is enabled
    And the same source event is collected twice
    When Gittan records evidence
    Then only one canonical shadow record should be retained for that event fingerprint

  Scenario: Report can use shadow evidence after upstream cleanup
    Given shadow logging captured events for a closed date window
    And the original source log has been removed or rotated
    When the user runs a report using retained evidence
    Then Gittan should still be able to include the retained events
    And the output should say the evidence came from the shadow log

  Scenario: Retention is local and explicit
    Given shadow logging is not enabled
    When the user runs a normal report
    Then Gittan should not create a durable shadow evidence store
    And the report should still complete from live sources
```

## Privacy And Safety

- Shadow logging must be opt-in until the UX is clear.
- The storage path must be documented and local.
- Deletion/export controls must be part of the design before broad rollout.
- Records should prefer normalized evidence over raw logs.
- Sensitive values should be redacted or hashed unless needed for review.
- The health monitor should report shadow-log state without exposing raw event
  details.

## Health Monitor Integration

The health surface should eventually show:

- shadow logging enabled / disabled,
- last capture time,
- records captured today,
- retention window,
- chain integrity status,
- sources with live evidence but no shadow retention.

This makes "reporting is healthy" mean both current capture and durable local
evidence are working.

## Open Questions

- Should the first implementation run only when a report/status command runs, or
  should there be a background launch agent?
- What is the default retention window?
- Should records store redacted detail only, with raw detail recoverable from
  live source logs when still available?
- Should per-source shadow logging be configurable?
- Should the deterministic replay tools consume shadow logs before live sources
  for closed windows?
