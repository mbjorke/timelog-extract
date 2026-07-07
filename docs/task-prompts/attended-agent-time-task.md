# Task Prompt: Attended vs agent time — report dimension (spec → slices)

## Traceability

- story_id: GH-284
- spec_status: draft
- implementation_status: in progress
- created_at: 2026-07-03
- last_updated_at: 2026-07-06
- implementation.pr: pending
- implementation.branch: task/attended-vs-agent-time-slice1
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-07-03: Initial draft from Timely benchmark findings (2026-07-02/03).

## Problem

A growing share of evidenced work is produced by background agents (Claude Code
loops, CodeRabbit runs, CI/merge automation) while the user's attention is in a
different window — or away entirely. The 2026-07-02 benchmark showed PRs being
merged and issues filed during periods a foreground-sampling tracker credited to
Chrome or logged as idle.

Gittan already **captures** this evidence (GitHub events, AI CLI logs) but the
report does not distinguish *attended* work from *delegated agent* work. That
leaves two problems:

1. **Reporting honesty:** a 3h session line can mix 1h of hands-on work with 2h
   of agents running unattended. Customers and the user deserve the split.
2. **Strategic:** foreground-sampling trackers (Timely Memory, ActivityWatch)
   structurally cannot see unattended work — attention-based capture assumes
   presence = work. Evidence-based capture is the only model that can label it.
   This is Gittan's clearest differentiator in the agent era.

## User value

- Honest session narrative: "attended 1.2h + agent 1.8h" instead of a flat 3h.
- A defensible answer to the coming billing question: *how do I report agent
  hours to a customer?* (Report first; billing policy stays human.)
- Partner/pitch demo: same day, evidence layer shows work no attention tracker
  can see.

## Non-goals

- No automatic billing of agent time (billable stays approval-gated; see
  `docs/specs/source-evidence-policy.md` layers).
- No new collectors in slice 1 — classification uses evidence already collected.
- No per-second attendance reconstruction; session-level labeling is enough.
- Not a replacement for the presence-estimated band (GH-146) — it composes with it.

## Behavior (target)

```gherkin
Feature: Sessions are labeled attended, agent, or mixed
  Evidence that occurred without user presence is reported as agent time,
  never silently blended into attended hours.

  Scenario: Background agent work during foreground absence
    Given a session contains GitHub delivery events and AI CLI activity
    And no attended evidence (user-authored prompts, browser, editor focus)
      overlaps those timestamps
    When the report is generated
    Then the session (or sub-span) is labeled "agent"
    And the day summary shows attended and agent hours as separate totals

  Scenario: Mixed session keeps the split visible
    Given a session interleaves user prompts with long agent task runs
    When the report is generated
    Then the session shows an attended/agent split, not a single undifferentiated total

  Scenario: Agent time is never billable by default
    Given a day with agent-labeled hours
    When billable totals are computed
    Then agent hours require the same explicit approval as all other time
    And the default invoice view keeps the attended/agent distinction visible

  Scenario: Uncertain attendance degrades honestly
    Given evidence where presence cannot be established either way
    When the report is generated
    Then the time is labeled attended (conservative default)
    And no time is dropped from the observed total
```

## Slices

### Slice 1 — attendance classifier + report label (priority: now)

- Classify each session (or sub-span) as `attended | agent | mixed` from
  existing evidence: user-authored prompt events, browser/editor activity, and
  presence signals (Screen Time; later the Timely-Memory/ActivityWatch presence
  sources) vs agent-only signals (GitHub events, task-notifications, loop logs).
- Surface in terminal report + truth payload (new field; bump payload contract
  consciously — extension consumers read `core/truth_payload.py`).
- acceptance: the four scenarios above pass on a fixture day modeled on
  2026-07-02 (night agent run, morning mixed session, unattended merges).
- validation: fixture test + one real-day manual comparison recorded in
  `private/benchmarks/`.

### Slice 2 — per-customer attended/agent split in review (priority: next)

- `Project-hour review` table gains an agent-hours column or annotation.
- Composes with work-unit v2 (GH-222) attribution.

### Slice 3 — narrative/invoice wording (priority: later)

- Executive narrative and invoice deliverable mention delegated agent work per
  period (AI-generated text per the invoice-text principle; never static config).

## Dependencies / open decisions

- Presence-estimated band (GH-146, built) — reuse its presence signals; do not
  duplicate.
- Work-unit v2 (GH-222 / #267) — session-splitting boundaries should align.
- Timely-Memory presence source (companion spec
  `timely-memory-collector-spike-task.md`) sharpens the classifier but is not a
  blocker; Screen Time + event-type heuristics suffice for slice 1.
- Decision needed: minimum span granularity for sub-session labeling (proposal:
  the existing session gap unit, no finer).
