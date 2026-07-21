# Backlog priority pass — 2026-07-21 (product-owner)

Full prioritization of the open issue backlog. Strategic context: outreach
email sent to Timely's CEO 2026-07-21 asking for a demo (answer window
~1–2 weeks); no external beta testers yet; a ~30-day personal runway frames
everything. Two governing questions for every item: *does it make the demo
land?* and *does it get an external user running Gittan?*

## Decision principles

1. **Demo-critical and tester-critical beats architecture.** The ledger
   refactor direction (GH-408/GH-410) is right, but only its `now` slices
   run ahead of the demo/tester threads.
2. **Accuracy bugs that corrupt the operator's own numbers are `now`.**
   A demo of a tool whose own hours are provably wrong is a liability
   (the 2026-07-13 evaporation case).
3. **Workflow/agent tooling is `later` for 30 days.** kanin-loop polish and
   auto-commit formalization do not move either governing question.
4. **Everything built must name its issue first** — restored governance
   after two ad-hoc builds on 2026-07-21 (spike + demo renderer; the
   renderer is retro-filed under #415).

## The board after this pass

### now
- **#415 Timely demo readiness** (new; governs PR #413 + rehearsed 3-beat
  script; masked mode one flag away)
- **#416 Beta onboarding dry-run** (new; not code-gated — the most
  important thread is a phone call, not a feature)
- **#414 Chrome dashboard-work evaporation** (new; per-URL-per-day thinning
  + downstream event drop; evidence loss before any session model)
- **#408 Commit events land in the shadow log** (already `now`; protects
  the only dataset the demo runs on)
- **#267 Work-unit v2 — report-first attribution** (already `now`; anchor
  implementation vehicle that GH-410 delegates to)

### next
- #410 Presence blocks + anchor attribution (drift-lint slice first)
- #254 Shadow log slice 1 (GH-151)
- #406 Anchor-plan bulk-apply guardrail (precedes work-unit v2 build,
  not its spike)
- #262 Worktree-invariant attribution via repo slug
- #222 gittan map: map to existing project
- #354 Research spike: Timely Memory evidence shapes (rises to `now` the
  day a demo call is booked)
- #327 / #332 attendance taxonomy + presence bracketing (feed block mode)
- #367 / #368 / #369 session-label enrichment calibration

### later (demoted this pass)
- #320, #272, #276 kanin-loop workflow items (were `next`) — agent
  workflow polish does not move the 30-day needle
- #237 gittan-data auto-commit formalization (was `next`)
- #317, #412 older PO-pass trackers (story-drift follow-ups stay tracked,
  not active)
- All previously-`later` items unchanged

### do not build yet
- #266 report-first work units brainstorm (unchanged)
- Own presence sampler (GH-410 item 3b; revisit trigger = Rosetta sunset)
- SQLite evidence store (GH-408 item 5)

## Housekeeping done in this pass

- Closed #407, #409, #411 as duplicates of open #317, #327, #332 (created
  by the 2026-07-20 docs-to-issues run whose story_ids pointed at older
  issues — the known multi-agent story-drift failure mode).
- #406 and #412 kept open despite pointing at closed #342/#365: the
  underlying specs are not implemented, so they remain the live trackers.
- PR #413 linked to #415 (`Closes #415` with the rehearsed script).

## Non-code threads this pass cannot label but which outrank most of it

1. Reply handling for the Timely email (earliest follow-up 2026-07-28,
   max one).
2. Beta tester outreach (issue #416 tracks the dry-run, not the calls).

## Traceability

- story_id: GH-317 lineage (successor pass; previous: 2026-07-08, 2026-07-10)
- spec_status: approved (this file records decisions already applied to
  the board)
- implementation_status: n/a (planning artifact)
- created_at: 2026-07-21
- last_updated_at: 2026-07-21
- implementation.pr: n/a
- implementation.branch: task/backlog-priority-2026-07-21
- implementation.commits: []
- validation.evidence: issue labels + closures visible on the board
- validation.decision: GO
- changelog:
  - 2026-07-21: Pass executed; labels applied; #407/#409/#411 closed as
    duplicates; #414/#415/#416 created; kanin-loop items demoted.
