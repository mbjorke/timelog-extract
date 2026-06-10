# Intent capture — recording user intention at the moment of work

Status: draft spec  
Last updated: 2026-06-10

## Purpose

Close the gap between **what Gittan observed** and **what the user was
actually doing**. This gap is the root cause of triage pain and cannot be
fixed by inference or review UX alone.

Today every classification signal is **retroactive**: an event like
`https://claude.ai/chat/<id>` carries no thread title, no semantic content,
and usually no adjacent context. A long-lived AI chat thread — often the
single most billable artifact of a working day — is unclassifiable after
the fact unless the user manually adds a `tracked_urls` entry.

Intent capture inverts this: the user signals *at the start of (or during)
a work session* which project a conversation/artifact belongs to. Triage
then becomes **confirmation** of mostly-classified events instead of
**archaeology** over weak signals.

## Non-goals

- No browser extension or capture UI in this spec — only the record
  contract and write path. Capture surfaces (bookmarklet, agent gateway,
  CLI command) are downstream consumers.
- No automatic classification changes without the existing
  `classify_project` path; intent records are an *input* to classification,
  not a bypass.
- No raw URL retention by default (see Privacy).
- No multi-user/team model.

## The intent record

Append-only JSONL at `~/.gittan/intent-capture.jsonl` (location follows
the canonical `~/.gittan/` config home; storage philosophy per
`docs/decisions/private-not-local.md`).

Proposed fields per record:

- `schema_version`: int (start at 1)
- `captured_at`: ISO-8601 timestamp (wall time of the tagging action)
- `project`: canonical project name (must match a configured profile)
- `url_hash`: stable hash of the normalized URL (default identifier)
- `url`: raw URL — **only when the user explicitly opts in**
- `source_hint`: optional, e.g. `claude.ai`, `chatgpt.com`, `lovable.dev`
- `note`: optional free text from the user
- `via`: capture surface, e.g. `cli`, `bookmarklet`, `agent-gateway`

URL normalization (strip fragments/query noise, lowercase host) must be
deterministic and shared with the Chrome/Lovable collectors so observed
events and intent records hash identically.

## Behavior Contract

```gherkin
Feature: Intent capture
  The user can record project intent for a work artifact at the moment of
  work, and classification consumes that intent later.

  Scenario: User tags a conversation to a project
    Given a configured project "project-alpha"
    When the user signals "this conversation belongs to project-alpha"
    Then a record is appended to ~/.gittan/intent-capture.jsonl
    And the record contains project, url_hash, captured_at, and via
    And the raw URL is not stored unless the user explicitly opted in

  Scenario: Classification consumes intent records
    Given an intent record maps url_hash H to "project-alpha"
    And a collector observes an event whose normalized URL hashes to H
    When classification runs
    Then the event is classified to "project-alpha"
    And the classification provenance says it came from intent capture

  Scenario: Re-tagging a long-lived thread
    Given an intent record maps url_hash H to "project-alpha"
    When the user later tags the same URL to "project-beta"
    Then a new record is appended (the log is never rewritten)
    And events after the new record's captured_at classify to "project-beta"
    And events before it keep "project-alpha"

  Scenario: Invalid project name is rejected
    Given no configured project named "ghost-project"
    When a capture surface submits an intent record for "ghost-project"
    Then the record is rejected with a clear error
    And nothing is appended to the log
```

The re-tagging scenario is the minimal viable model for **long-lived
threads that span projects**: time-segmented attribution via append-only
re-tag events, aggregated at report time. No config rewriting.

## Privacy

- Hash by default; raw URL is explicit opt-in per capture (or a global
  opt-in the user sets knowingly).
- The log is user-readable plain JSONL in the user's own config home —
  inspectable, deletable, syncable on the user's terms.
- Capture surfaces must never auto-capture; every record requires a
  deliberate user action.

## Dependencies and relations

- `docs/decisions/private-not-local.md` — storage philosophy; allows a
  synced `~/.gittan/` so capture can happen from any device.
- `docs/specs/local-evidence-shadow-log.md` — intent records are exactly
  the kind of evidence worth shadow-retaining; fingerprint/hash mechanics
  should be shared.
- `docs/specs/scheduled-reported-time-bridge.md` — intent capture feeds
  classified time; it is upstream of reported/approved layers.
- `docs/specs/ab-rule-suggestions.md` — an accepted intent record for a
  recurring host is a natural rule-suggestion trigger ("always map this
  host/thread to project X?").

## Open questions

- Write path for non-CLI surfaces: what authenticates a bookmarklet or
  agent gateway writing into `~/.gittan/`? (A synced folder sidesteps a
  local HTTP endpoint entirely; an agent with terminal access can use the
  CLI. Decide before building any capture surface.)
- Should `gittan report` surface "intent-tagged but never observed"
  records as a hygiene signal?
- Retention/compaction policy for the JSONL log.
- Should accepting an intent record optionally write a durable
  `tracked_urls` entry, or stay a separate evidence stream forever?
