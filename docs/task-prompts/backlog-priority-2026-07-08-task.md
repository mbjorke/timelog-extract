# Backlog priority pass — 2026-07-08 (product-owner)

Product-owner planning pass ordering the **whole open backlog** as of 2026-07-08.
No code is changed here — this is the ordered, behavior-ready backlog and the
prioritization decisions behind it.

**Decision filter (from `docs/product/gittan-vision.md`):** does the next
`gittan report` / invoice show the operator the *right* hours for their acceptance
window? Trust and local-first are non-negotiable; agent (non-attended) hours must
never silently become billable. A second, operational filter applies this week:
**does it stop the multi-agent story-drift that is costing whole days?**

## Traceability

- story_id: `GH-317`
- spec_status: `draft`
- implementation_status: `not built` (planning artifact — no code)
- created_at: `2026-07-08`
- last_updated_at: `2026-07-08`
- implementation.pr: pending
- implementation.branch: `task/backlog-priority-2026-07-08`
- implementation.commits: []
- validation.evidence: this backlog + issue label state after the pass
- validation.decision: `GO` (as a planning deliverable)
- changelog:
  - `2026-07-08: Initial priority pass; bumped #272 later→next; documented multi-agent story-drift finding.`

## Finding: multi-agent story handling drifts (why this pass exists)

Investigation of PR/issue/commit activity 2026-07-01 → 2026-07-08 confirmed the
operator's suspicion — different agents handle stories differently, and the board
lags reality:

- **Identity collision.** Nearly all PRs are authored as `mbjorke` even when written
  by an agent (Cursor: 37 co-author trailers; Claude Opus/Fable; CodeRabbit). Only
  `google-labs-jules[bot]` commits under its own identity. On the board everything
  looks maintainer-authored → you cannot tell who did what. (Tracked in #272.)
- **The "giant story."** GH-284 (attended vs agent time) ran as **13 Jules commits**
  across 2026-07-06 19:45 → 2026-07-07 11:07 UTC — six near-identical
  "classification" commits then "fixes / address review findings / final fixes":
  classic autonomous churn on one branch for ~a day. Merged as #310, yet issue #284
  still read `impl: not built` until this pass.
- **Inconsistent issue linking.** Of ~46 PRs since 2026-07-01, only ~10 used
  `Closes #N`; the rest left the story un-synced. Fixed at source by the new
  `AGENTS.md` → *Pull requests (issue linking)* rule (`Closes` / `Part of #N`).
- **Two parallel ID systems.** `GH-NNN` (story id in the spec) vs `#NNN` (GitHub
  issue/PR number) do not map 1:1 (story `GH-186` = issue `#263`). 18 of 31 open
  issues carry a `GH-` id in the title; agents cite one, the other, or both.
- **Uneven slice discipline.** Some agents slice and say so ("slice 1/2", "slice 1");
  others ship monolithic.

**Consequence for prioritization:** the two `now` items (#263 Phase 4, #284 slice 2)
both touch the **billable/invoice** surface and *will* collide if two agents pick
them up independently — the exact failure pattern above. They must be sequenced and
owned by one lane (see `now` tier).

## `#272` decision: bump `later → next` (not `now`)

**Yes, raise it — to `next`.** Rationale: today's whole session was spent
untangling drift, so the operational cost is real and recurring. But the *cheap
half* — linking discipline — just shipped as docs (`Closes`/`Part of` rule), so
#272's remaining value is the **identity/ownership** half (which agent owns which
lane under a shared git identity). That is worth a `next` slice but must not preempt
the two report/invoice-accuracy `now` items, which sit closer to the sacred contract.

---

## `now`

### #263 Phase 4 — invoice reads the confirmed reported-time layer

- problem: invoice/billable still reads raw observed hours, not the operator-confirmed
  `reported_time` layer that Phases 1–3b already built and merged.
- user value: the invoice line reflects what Marcus actually confirmed (incl. manual
  additions), not raw evidence — the whole point of the reported layer.
- non-goals: Phase 5 GUI; the Calendar collector; changing session math.
- behavior:

```gherkin
Scenario: Invoice uses confirmed reported time
  Given confirmed reported_time exists for Project Alpha in the billing window
  When the invoice/billable total is computed
  Then it uses the confirmed hours, not the raw observed hours

Scenario: Fallback before adoption
  Given no reported_time exists for the window
  Then the invoice falls back to today's observed behavior unchanged
```

- acceptance: invoice/PDF + billable totals read the confirmed layer with the
  documented fallback; full `bash scripts/run_autotests.sh` green; no file > 500 lines.
- validation: operator-local acceptance window on real config (timestamped copy,
  never destructive edits); diff observed-vs-confirmed invoice output.
- dependencies: Phases 1–3b (merged). **Coordinate with #284 slice 2** — same surface.

### #284 slice 2 — attended/agent split reaches billable + invoice

- problem: slice 1 (#310) surfaces attended vs agent in the report/JSON, but billable
  totals and the default invoice view do not yet honor the split.
- user value: trust — autonomous agent hours are never silently billed; the operator
  approves them like any other time.
- non-goals: re-deriving the classifier (shipped); the Lovable-parity tweak (#313,
  `next`).
- behavior:

```gherkin
Scenario: Agent time is never billable by default
  Given a day with agent-labeled hours
  When billable totals are computed
  Then agent hours require the same explicit approval as all other time
  And the default invoice view keeps the attended/agent distinction visible

Scenario: Uncertain attendance degrades honestly
  Given evidence where presence cannot be established
  Then the time is labeled attended (conservative default) and no time is dropped
```

- acceptance: billable + invoice honor attendance labels with the conservative
  default; regression tests extend `tests/test_attendance_classification.py`; suite green.
- validation: report + invoice on an acceptance window showing a visible
  attended/agent split; agent hours excluded from default billable.
- dependencies: #310 (merged). **Sequence with #263 Phase 4** — both edit the
  billable/invoice path. Recommend: one lane does #284 slice 2 first (don't-bill
  correctness), then #263 Phase 4 (confirmed-layer read) on top, or land them as one
  coordinated work-unit. Do **not** run them as two independent agent branches.

---

## `next`

- **#313** Attendance: Lovable = attended (parity with Cursor/Claude) — small, pairs
  with #284; fold in during slice 2 if cheap.
- **#272** kanin-loop: agent↔task ownership (identity half) — *bumped from later.*
  Make agent authorship and lane ownership legible under the shared git identity.
- **#276** kanin-loop handoff/preflight polish — reduces the stale-cache confusion
  seen today (the 09:56 `preflight.json` that misreported PR state).
- **#238** slice 2 — consolidate remaining 4 deprecated commands (`triage`,
  `triage-apply`, `suggest-rules`, `apply-suggestions`) into `review`; needs the
  careful test refactor #309 deferred.
- **#262** Worktree-invariant attribution via git remote/repo slug — attribution
  correctness; feeds the report contract.
- **#254** Local Evidence Shadow Log — Slice 1 (measure-first) — durability backbone.
- **#237** Formalize gittan-data auto-commit as `gittan setup` — data-safety hardening.
- **#265** Post Gittan hours to Toggl (`gittan toggl-sync`) — external posting; must
  read the confirmed layer (depends on #263 Phase 4 landing first).
- **#267** Work-unit v2 — report-first attribution — large; keep `next`, not `now`,
  until the two invoice-surface items settle (avoid another all-day churn story).
- **#222** gittan map: cannot map to existing project; merge UX — real bug, but
  partly superseded by work-unit v2 direction; keep `next`.

## `later`

Unchanged from current labels: #230, #239, #241, #242, #245–#253, #255, #256, #257,
#264, #294. These stay in the task-prompts / issues until promoted by a future pass.

## `do not build yet`

- **#266** Brainstorm: report-first work units (agenda handout) — an agenda, not a
  build item.

---

## Label changes applied by this pass

- **#272**: `priority:later` → `priority:next`.
- All other `now`/`next`/`later` labels already match this ordering; no churn.

## Open decisions for the maintainer

1. Sequence for the two `now` items: single coordinated work-unit vs #284-slice-2-then-#263-Phase-4. (Recommendation above.)
2. Whether to retire the `GH-NNN` story-id convention in favor of `#NNN` alone (would
   remove the dual-ID confusion but touches many specs) — candidate for #272 scope.
