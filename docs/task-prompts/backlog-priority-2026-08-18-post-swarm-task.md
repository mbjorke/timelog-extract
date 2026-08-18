# Backlog priority pass — 2026-08-18 post-swarm (product owner)

Planning pass **after** the afternoon swarm merged to `main`:

| Merged | What landed |
| --- | --- |
| #557 → #549 | `GITTAN_HOME` one data directory (verified on `origin/main`) |
| #558 → #521 | `gittan status` never exits mute |
| #556 → #448 | Lovable Desktop ambient ≠ authorship |
| #559 → #544 | **Phase 1** title-first Cursor attribution (`Part of`) |
| #560 → #414 | **Slice** tracked-URL heartbeat (`Part of`) |

No feature code in this pass: re-order `now`/`next`, close the morning
planning issue as superseded, and name the remaining slices.

Successor to `backlog-priority-2026-08-18-task.md` (GH-554 / #554).

## Traceability

- story_id: `GH-563` (https://github.com/mbjorke/timelog-extract/issues/563)
- spec_status: approved
- implementation_status: not built (planning artifact — no code)
- created_at: 2026-08-18
- last_updated_at: 2026-08-18
- implementation.pr: pending
- implementation.branch: `task/backlog-priority-2026-08-18-post-swarm`
- implementation.commits: []
- validation.evidence:
  - labels: #550 → now; #561 → next; #414 → next; #554 closed superseded
  - this pass: #563
  - shipped today: #549 #521 #448; partial #544 #414
  - successor to `backlog-priority-2026-08-18-task.md` (GH-554 / #554)
- validation.decision: GO
- changelog:
  - 2026-08-18: Post-swarm pass. Finish #544 scenario 3 first (unblocked by
    #549). Promote #550. Demote #561 Framer and #414 remainder. Record
    process lesson: `NEEDS_HUMAN` must not squash-merge on ambiguous "yes".

Labels remain the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`).

---

## Finding: the swarm moved trust; leftovers are slices

The morning pass put `#549` then `#544` at the top. Both are partially done:

- **#549** — closed; live isolation check on `origin/main` PASSed (resolver +
  36 unit tests + real observed hashes unchanged under temp `GITTAN_HOME`).
- **#544** — title-first + conflict nudge shipped; **scenario 3**
  (observed→rescan re-attribution nudge) still open and now unblocked.
- **#414** — Claude/Gemini tracked-URL heartbeat shipped; **dashboard/infra**
  evaporation still owned by `#410` (`priority:later`). Keeping `#414` in
  `now` would pretend the blocker is gone.

**#561 Framer** joined `now` as a new source story. Vision filter (*practical
over perfect*; trust first): finishing an open trust scenario and the privacy
guard outrank a new presence-only source.

## Finding: process — `NEEDS_HUMAN` was merge-skipped

The swarm PRs classified `NEEDS_HUMAN` (collectors / report / observed). The
maintainer said "ja" to merge-gate **and/or** ordered merge; the agent
squash-merged all five without `rabbit_loop --manual-test-plan`. That violated
the ship gate in `docs/skills/rabbit-loop.md`.

**Rule for next sessions:** ambiguous assent to "merge-gate and/or merge"
means run the gate and **report**; do **not** squash-merge `NEEDS_HUMAN`
items unless the maintainer says explicitly e.g. "merga dem ändå" /
"merge the NEEDS_HUMAN ones".

---

# Ordered backlog

## now

### 1. GH-544 — finish re-attribution nudge (scenario 3)

- priority: **now** (top — completes the open trust bug)
- problem: period column can still contradict an earlier split without notice;
  phase 1 stopped silent *moves*, not silent *undetected* moves vs observed.
- user value: operator sees what moved and why when a re-scan disagrees with
  the keep-max cache.
- non-goals: live ask / #540; lifetime substrate (#543); redoing title-first.
- behavior: issue scenario 3 — earlier attribution not contradicted without
  notice; instrument `scripts/reconcile_snapshot.py` shift-share falls.
- acceptance: fixture + optional local instrument; numbers stay off GitHub.
- validation: tests on observed-cache diff + nudge; live check only under
  `GITTAN_HOME` sandbox.
- dependencies: **#549 done** — safe to validate against live config in a
  sandbox.

### 2. GH-550 — hook-guard follow-ups (default path live)

- priority: **now** (promoted from `next`)
- problem: data-directory guard shipped in 0.4.2; default branch
  `${GITTAN_HOME:-$HOME/.gittan}` still under-tested; other post-merge gaps
  remain (stale hook on disk, containment, tilde/relative shapes).
- user value: every ordinary install takes the default path; #549 fixed
  relocation — this proves the default.
- non-goals: redoing #549 resolver; expanding into #543.
- acceptance: tests execute the default branch (no `GITTAN_HOME` set);
  doctor/stale-hook signal if cheap; ranked items from the issue.
- validation: unit/hook tests; no live config required for the default-path
  coverage gap.
- dependencies: after #549 (done).

### 3. GH-515 — prevent client data in issues / PRs / comments

- priority: **now** (unchanged)
- problem: working-tree guard cannot see GitHub text; paste + bot
  amplification.
- user value: prevention still outranks leftover #431 cleanup.
- spec: `docs/task-prompts/prevent-client-data-in-issues-task.md`
- dependencies: maintainer confirms Actions secret for term list.

### 4. GH-431 — remaining client-name triage (parked human)

- priority: **now** (parked — do not block agents)
- progress: #551 / #552 reduced the tree; thread decision still open.
- **NEEDS_HUMAN:** mask vs delete on the comment thread; doc replacements.

## next

### GH-561 — Framer as a Gittan source

- priority: **next** (demoted from `now`)
- problem: presence in Framer is measurable; "design work" is not; shadow log
  is a precondition (not backfillable).
- why demoted: new source after trust leftovers; honest presence-only scope is
  valuable but not the scarce next hour.
- promote when #544 scenario 3 and #550 are done, or when maintainer wants a
  source week.
- spec: `docs/task-prompts/framer-source-task.md`

### GH-414 — Chrome dashboard/infra remainder

- priority: **next** (demoted; tracked-URL slice shipped in #560)
- remainder: keyword-gated `collect_chrome` / Uncategorized drop for
  infra/dashboard hosts — **owned by #410** (`priority:later`).
- do not pretend #414 is agent-ready until #410 moves up or is sliced.

### GH-543 — lifetime substrate (reopened)

- priority: **next** (unchanged)
- keep-max vs append-only evidence (#254); after #544 nudge.

### Unchanged / still next (selected)

#540, #531, #527, #524, #523, #416 (parked evening), #408, presence/label
family (#327, #332, #367–369), #254, setup/write-safety cluster.

## later / do not build yet

- Live operator-ask / full #540 enforcement until provenance product call.
- #410 presence-blocks (blocks #414 remainder) — stays later unless promoted.
- No other band moves this pass.

## Non-goals for this pass

- Implementing any of the above.
- Auto-merging further `NEEDS_HUMAN` work without explicit assent.
- Board field writes unless `project` scope available.

## Decisions for the maintainer

1. **Order confirmed (post-swarm):** #544 scenario 3 → #550 → #515; #431
   parked human; #561 and #414 remainder demoted to `next`.
2. **#515** — still need Actions-secret confirmation.
3. **#431 thread** — mask vs delete (still open).
4. **#416** — still needs a named re-promotion evening.
5. **Process:** confirm the "NEEDS_HUMAN never merges on ambiguous ja" rule.
6. **#554** — close as superseded by this pass's issue.
