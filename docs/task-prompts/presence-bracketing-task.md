# Task Prompt: Presence brackets evidenced sessions (composition time at edges)

Maintainer concern (2026-07-08): evidence-first measurement has started to feel
*too* exact — time spent reading, thinking, and composing text before the first
evidence event (a sent prompt, a page visit) leaves no event and silently
vanishes. This is the opposite failure mode from Timely, which sees all presence
but attributes it poorly (2026-07-07 benchmark: Timely booked the operator's own
product work to a client and dumped 1.6h of real client work in Unassigned).

**Strategic frame:** Gittan already pitches as a *complement* to Timely — the
Timely Memory local buffer is an ingested source since #285/#290
(`core/timely_memory.py`). This spec upgrades presence from *comparison* to
*bracketing*, and names the longer path to owning the presence signal natively.

## Traceability

- story_id: `GH-332`
- spec_status: `draft`
- implementation_status: `in progress`
- created_at: `2026-07-08`
- last_updated_at: `2026-07-09`
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/339
- implementation.branch: `task/presence-edge-gap-measure`
- implementation.commits: `[a6c96ba, 6e4362d, a7973fa]`
- validation.evidence: operator report with `--timely-memory-source on` — Edge gap row + Bracketable preview; observed hours unchanged; unique edge gap materially smaller than naive per-session sum. Slice 1 measures only; Slice 2 (bracket) not built.
- validation.decision: `conditional GO`
- changelog:
  - `2026-07-08: Initial draft from maintainer composition-time concern + Timely benchmark.`
  - `2026-07-09: Slice 1 started — Timely Memory spans + edge-gap diagnostic (no hour changes).`
  - `2026-07-09: Unique wall-clock totals + capped bracketable preview; PR #339.`
  - `2026-07-09: Canonical traceability enums (Qodo); exclusive-end presence containment.`

## Problem

`compute_sessions` spans **first event → last event** (15-min gap merge), with
min-session floors for lone events. Time *between* events inside a session is
counted, but the **edges leak**: ramp-up before the first event, ramp-down after
the last, and pure thinking/composition that never emits an event. As collectors
get more precise, this systematically undercounts attended work — the exact
opposite of the trust promise ("finds all your time").

## What already exists (do not rebuild)

- **Presence signals collected:** Screen Time and Timely Memory, both role
  `COVERAGE_COMPARATOR` in `core/sources.py` — "comparator context, never
  billable input". Used today only to *compare* totals (evidence 5.2h vs
  presence 8h), never to stretch sessions.
- **Presence-estimated layer:** `core/presence_estimated.py` (display-only).
- **Native-presence path:** `docs/sources/activitywatch-integration.md` (backlog).

## Direction — three layers

1. **Pitch (built):** Gittan complements Timely. Their Memory buffer feeds
   Gittan; Gittan supplies the attribution Timely lacks. Keep this working.
2. **Bracketing (this spec):** when a presence comparator shows continuous
   presence adjacent to an evidenced session, extend the session span to cover
   the ramp. Presence **brackets** evidence — it never *creates* attribution
   (project identity always comes from evidence events).
3. **Native presence (later):** ActivityWatch (or own sampler) so the presence
   signal doesn't depend on a competitor's local buffer. Promote
   `activitywatch-integration.md` when layer 2 proves value.

## Behavior (target)

```gherkin
Scenario: Ramp-up before the first event is captured
  Given continuous presence from 09:55 and an evidenced session starting 10:00
  When the report is generated
  Then the session start extends toward 09:55, capped at the edge limit
  And bracketed minutes are visibly labeled, not silently merged into evidence

Scenario: Presence never invents attribution
  Given presence with no evidenced events in a window
  Then no project time is created from presence alone

Scenario: Billable stays gated
  Given bracketed session minutes
  Then they follow the same approval path as all other time
  And the presence-vs-authorship taxonomy (GH-327 / #327) applies

Scenario: No presence source, no change
  Given neither Screen Time nor Timely Memory covers the window
  Then sessions behave exactly as today (pure evidence spans + floors)
```

## Slices

### Slice 1 — measure the edge gap (priority: now)
- For each evidenced session, compute how much adjacent continuous presence
  exists (per edge, per day). Surface as a report diagnostic — no hour changes.
- Value: quantifies the undercount before we change any totals (measure-first,
  same pattern as #254).
- Implementation: `core/presence_edge_gaps.py` + Timely Memory span return from
  `collect_timely_memory`. Terminal Review summary row **Edge gap (presence)**;
  truth payload key `presence_edge_gaps`. Requires `--timely-memory-source on`.
  Screen Time remains day-totals only (no span edges yet).

### Slice 2 — bracket with cap + label (priority: next, after slice-1 data)
- Extend session spans into adjacent presence, capped (default e.g. 10 min/edge,
  configurable). Bracketed minutes labeled in terminal/JSON (`bracketed_hours`).
- Billable treatment decided together with #327 (presence-only tier).

### Slice 3 — native presence source (priority: later)
- Promote ActivityWatch integration; Timely Memory demoted to optional comparator.

## Non-goals

- Replacing evidence attribution with presence (Timely's failure mode).
- Keystroke/input logging.
- Changing billable defaults ahead of the #327 decision.

## Dependencies / open decisions

- #327 — presence ≠ authorship taxonomy (billable gating for bracketed minutes).
- Edge cap default and whether bracketing needs per-project opt-in.
- Related: #251 (Screen Time gap recalibration), #285/#290 (Timely Memory).
