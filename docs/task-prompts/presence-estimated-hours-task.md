# Evidenced hours + labeled presence-estimated band

> Supersedes the earlier "presence-confirmed gap bridging" framing. We do **not**
> mix estimated time into `observed`/billable. Instead we show two clearly
> labeled numbers and let the user decide what to bill.

## Backlog item

- **priority:** next (the highest-value accuracy work after the GH-146 net)
- **problem:** On test/debug-heavy days the user works continuously but produces
  few high-signal, timestamped events. Gittan can only honestly count evidenced
  events, so the total badly under-represents a real full day — yet inflating it
  is fabrication. There is no honest middle number to *compute*; there is only an
  honest *floor* and an honest *presence-bounded estimate*.
- **user value:** The real magnitude of a working day is visible (not lost to a
  5h floor) without ever fabricating billable time.
- **non-goals:**
  - Do NOT add estimated time to `observed`, billable totals, or the truth-payload
    hours that downstream/invoice consumers read.
  - Do NOT count IDE log-line volume as work.
  - Do NOT change the over-attribution guardrail (`core/sanity_bounds.py`).

## Why this shape (diagnostics, 2026-06-11, a confirmed test-heavy Cursor day)

| Finding | Value |
|---|---|
| Evidenced (honest event-based) | 5.54h |
| Old composer full-span fabrication | 14.60h (≈ Screen Time by accident) |
| Screen Time (presence) | 15.1h |
| Cursor log lines | 407k, ~96% IDE background chatter, not work |
| Claude Code CLI messages on 06-11 | ~2 (06-11 was a Cursor day; 06-12 had 897) |
| Cursor per-message/per-action timestamps | **none exist** (bubbleId/checkpointId/agentKv carry no time field; only composer header createdAt/lastUpdatedAt) |

**Hard constraint:** there is no dense honest temporal signal for Cursor-heavy
days. So the only honest options are (a) the evidenced floor and (b) a presence-
bounded estimate that is *explicitly an estimate* — never reconstructed evidence.

## Design: two numbers, never mixed

For each project (and the day/period total) compute and display:

1. **Evidenced** — exactly today's event-based hours. Unchanged. This is what
   feeds billable totals and the truth payload. The honest floor.
2. **Presence-estimated** — an explicitly labeled estimate of likely worked time,
   bounded by measured presence. Display-only; never billable without explicit
   user action.

### How the estimate is derived (presence-bounded, never fabricated)

- **Presence source:** Screen Time (per day). If unavailable for a day, the
  estimate is omitted for that day (no estimate, no guess).
- The estimate fills toward presence the evidenced gaps that sit *between* a
  project's own events (soft work: CI waits, reviews, iterative test runs),
  capped so the day's estimated total never exceeds Screen Time for that day.
- It is attributed to the project that dominates the surrounding evidenced
  events; gaps with no bracketing project signal are not attributed.

### Anti-fabrication invariant

```gherkin
Feature: The presence estimate is honest and never billable by default
  Estimated hours are labeled, bounded by presence, and separate from billable.

  Scenario: Estimate never exceeds measured presence
    Given a day's presence-estimated hours
    Then they never exceed that day's Screen Time

  Scenario: No presence means no estimate
    Given Screen Time is unavailable for a day
    Then no presence-estimated number is shown for that day

  Scenario: Estimate never touches billable or truth-payload hours
    Given a report is produced
    Then observed/billable totals and truth_payload hours equal the evidenced number
    And the presence-estimated value is a separate, labeled field

  Scenario: Estimate fills only between a project's own events
    Given a project's first evidenced event at 09:00 and last at 20:00
    Then no estimated time is attributed before 09:00 or after 20:00
```

## How it is shown (report surface)

- Terminal: an extra clearly-labeled column or line, e.g. `Evidenced` and
  `Est. (presence)`, with the estimate in a muted/italic style and a one-line
  legend stating it is a Screen-Time-bounded estimate, not billable.
- Truth payload: add a separate optional field (e.g. `presence_estimated_hours`)
  alongside the unchanged evidenced hours; version bump only if required.
- Never shown where it could be mistaken for billable (invoice/PDF excluded).

## Acceptance criteria

- `observed`, billable totals, and truth-payload evidenced hours are byte-for-byte
  unchanged vs today on every day.
- Presence-estimated value is present only when Screen Time exists, never exceeds
  Screen Time, and is visibly labeled as an estimate.
- On 2026-06-11 the report shows evidenced ≈ 5.5h and a presence-estimate between
  5.5h and 15.1h.
- Full autotest suite green; no file exceeds 500 lines.

## Validation

| Scenario | Evidence |
|---|---|
| Evidenced unchanged | Golden eval + existing hour tests unchanged |
| Estimate ≤ presence | Unit test on the estimate function |
| No Screen Time → no estimate | Unit test with empty screen_time_days |
| Estimate excluded from billable/PDF | Unit/integration test on invoice path |

## Open decisions (product owner)

1. **Gap bound for the estimate fill** (how long a between-events gap counts as
   soft work): 30 vs 45 vs 60 min. Larger = estimate sits closer to presence.
2. **Presence cap fraction:** 100% of Screen Time (user's earlier preference) vs
   a haircut (e.g. 85%) to exclude obvious personal/idle screen time.
3. **Surface scope:** show the estimate in `report` only, or also `status`?

## source-collector contract notes

- Screen Time gains an explicit **presence/corroboration role** (not a billable
  source). Document in `docs/specs/source-evidence-policy.md`.
- `collector_status` should report presence availability so the report can explain
  when/why the estimate is shown or omitted.

## Traceability

- story_id: GH-146
- spec_status: approved
- implementation_status: built
- created_at: 2026-06-15
- last_updated_at: 2026-06-15
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/147
- implementation.branch: task/repo-time-totals
- implementation.commits: []
- validation.evidence: tests/test_presence_estimated.py; maintainer 2026-06-11 Cursor day (5.5h evidenced → 15.1h presence cap)
- validation.decision: conditional GO
- changelog:
  - 2026-06-15: Initial draft created.
  - 2026-06-15: Implemented display-only presence estimate; terminal Delta (est.) primary.
- supersedes: the gap-bridging-into-observed approach (rejected: mixing estimate
  into billable)
- related: GH-146 net (`core/sanity_bounds.py`), composer burst-per-touch fix,
  evidence-gap-recalibration-task.md, `docs/specs/cursor-evidence-ceiling.md`
