# Backlog priority pass — 2026-07-26 (product owner)

Planning pass after **PR #469** (`task/session-capture-and-intent`) — the week's
largest product step: device session capture + session intent binding. No feature
code in this pass: priority, board Status, story-id hygiene, and what the close
of that loop does to neighboring work.

## Traceability

- story_id: `GH-472` (https://github.com/mbjorke/timelog-extract/issues/472)
- spec_status: approved
- implementation_status: not built
- created_at: 2026-07-26
- last_updated_at: 2026-07-26
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/469
- implementation.branch: task/session-capture-and-intent
- implementation.commits: []
- validation.evidence: this document (planning pass; labels + board writes)
- validation.decision: GO
- changelog:
  - 2026-07-26: Initial pass. Created #470 / #471 (story_ids had collided with
    unrelated #464 / #465) and #472 for this PO doc. Board Status for
    #469/#470/#471 → Needs manual testing; priority:now issues
    #408/#414/#416/#448 → Ready (were stuck in Backlog on Project 3 view 2).
  - 2026-07-26: Walkthrough follow-up from the maintainer's Claude session.
    Filed #473 (git-commit hook `No module named 'core'`, `priority:now`) and
    #474 (Cursor capture + device labels on report, `priority:next`, Gherkin in
    `capture-cursor-and-device-labels-task.md`). Clarified that #469 stores
    device but only captures Claude surfaces today — cloud was the forcing
    case; phone/desktop visibility in the report is still missing.

## Context: we are sewing the bag shut

Until this week, two gaps made the accuracy story incomplete:

| Gap | Before | After #469 |
|---|---|---|
| Evidence dies with the machine | A phone / cloud container transcript never reached `~/.gittan` | `gittan capture` + per-device ledger filing (#470) |
| Chat hours with no repo / URL | Only fix was a `match_term` that spilled forever | `gittan intent` binds one decision to one session (#471) |

Together they close the loop the vision already promised: **find the time**, then
**attribute it without inventing a permanent rule**. That is why this is the
week's largest progress — not because of line count, but because neighboring
attribution / evidence / triage work finally has the missing joints.

Labels remain the priority source of truth
(`docs/decisions/backlog-priority-surfaces.md`). Project 3 is the human view.

## Finding: the board could not see the progress

1. **No issues existed** for the two shipped specs. Traceability claimed
   `GH-464` / `GH-465`, but those numbers already belonged to unrelated issues
   (#464 backlog-surfaces decision; #465 Bolt date parsing). PR #469 closed
   nothing GitHub could act on.
2. **PR #469 was absent** from Project 3 Status until this pass.
3. **`priority:now` ≠ board Ready.** #408, #414, #416, #448 carried
   `priority:now` labels but sat in board column **Backlog** — exactly the drift
   view 2 was showing as "status is wrong."

## Actions taken this pass

| Action | Result |
|---|---|
| Create tracker issues | [#470](https://github.com/mbjorke/timelog-extract/issues/470) capture, [#471](https://github.com/mbjorke/timelog-extract/issues/471) intent — `priority:now` |
| Link PR | PR #469 `Closes #470` + `Closes #471` |
| Board Status | #469 / #470 / #471 → **Needs manual testing** (PR classification NEEDS_HUMAN) |
| Board Status | #408 / #414 / #416 / #448 → **Ready** (match `priority:now`) |
| Spec Traceability | `device-session-capture-task.md` → GH-470; `session-intent-binding-task.md` → GH-471 |

---

# Ordered backlog (re-read after #469 + walkthrough)

## Walkthrough result (2026-07-26, maintainer machine)

Already exercised: `evidence` (20559 records, chain OK, last capture today EEST),
`doctor` (Device coverage + capture-errors), `intent` ("nothing to ask" —
correct: today's Uncategorized Lovable row has no session anchor → `review`,
not `intent`), `report --today`.

**What #469 actually delivers today**

| Layer | State |
|---|---|
| Per-device ledger filing + `source_provenance.device` | **built** |
| Capture sources | **`claude-code` + `desktop-code` only** — cloud/container was the forcing case; phone vs Mac is stored when capture runs on that device, but Cursor is not captured this way |
| Device visible in report slugs | **not built** — doctor sees `Mac.lan`; report still says bare `timelog-extract` |
| Gherkin for phone/desktop *visibility* | **was missing** → now in `capture-cursor-and-device-labels-task.md` (#474) |

## now

### 1. GH-473 — git-commit hook: `No module named 'core'`

- priority: **now** (new; living evidence gap)
- problem: hook imports `core.evidence_store` under a bare `python3`; doctor
  already flags recurring capture failures; 24 git-commit rows vs constant
  commits.
- user value: commit wall-clock evidence stops vanishing silently.
- non-goals: fixing inside #469; rewriting the whole hook platform.
- behavior:

```gherkin
Scenario: A commit is recorded even when core is not importable in the hook
  Given the global post-commit hook fires
  And python3 cannot import the gittan package
  When the commit is recorded
  Then a spool file under ~/.gittan receives the git-commit event
  And the next gittan report or capture run drains the spool into the ledger
```

- acceptance: doctor stops showing the recurring import error after a normal
  commit + one gittan drain; fixture covers "no core on sys.path".
- **agent-ready enough once spool path is agreed** — default proposal: spool,
  don't import.

### 2. GH-470 + GH-471 / PR #469 — finish manual gate → merge

- priority: **now**
- Walkthrough largely done; remaining judgment: merge when CI + review threads
  are clear. Board: **Needs manual testing** until merge, then Done.
- **NEEDS_HUMAN** (merge / final sign-off)

### 3–6. Unchanged `priority:now` (board Ready)

| Issue | Why still now |
|---|---|
| #408 | Markdown worklog-as-view over the ledger |
| #414 | Chrome dashboard-work evaporation |
| #416 | Beta onboarding dry-run |
| #448 | Lovable Desktop open-app ≠ authorship |

## next

### 1. GH-474 — Capture Cursor + show device on report labels

- priority: **next** (new; Gherkin drafted)
- problem: capture is Claude-shaped; device is invisible in the report the
  operator reads. Phone vs desktop (and Cursor on another machine) is the
  unfinished half of "a phone is a machine too."
- user value: `timelog-extract (Mac)` vs `timelog-extract (iPhone)` in the
  narrative; Cursor sessions survive `gittan capture` like Claude Code.
- non-goals: Claude mobile app (no local artifact); changing fingerprints so
  two devices double-count the same action; billing identity splits.
- spec: `docs/task-prompts/capture-cursor-and-device-labels-task.md`
- dependencies: #470 merged (or available on the branch used to implement).

### 2. Intent asked inside the agent (MCP surface)

- priority: **next** (promote to task-prompt + issue when #471 is Done)
- Spec draft only: `docs/specs/intent-capture-agent-surface.md`.

### Neighboring issues that change meaning (not band)

| Issue | Band | Effect of #469 |
|---|---|---|
| #248 Claude Desktop Code/Chat evidence | `later` | Code verified (#141); #469 adds capture wiring. Re-scope to **Chat-only** or close. |
| #254 Shadow log slice 1 | `next` | Residual tracking; do not restart foundation. |
| #267 Work-unit v2 | `next` | Intent complements; does not replace. |
| #408 / #473 | `now` | #473 is the hook import hole left beside #408's "commits in the ledger" story. |
| #410 Presence blocks | `later` | Intent outranks match_terms for bound sessions only. |

## later / do not build yet

No further band moves. Re-read when #469 merges.

## Non-goals for this pass

- Implementing Cursor capture or device labels (spec + issue only).
- Implementing the MCP intent surface.
- Closing #248 / #254 without a dedicated hygiene PR.

## Decisions for the maintainer

1. **Merge #469** when satisfied — walkthrough already exercised the main paths.
2. **#473 spool design** — confirm "spool file → next gittan drain" before an
   agent implements (default in the issue body).
3. **#248** — close as verified for Code, or retitle to Chat-only.
4. **Friendly device names** (`Mac` vs `Mac.lan`) — nice-to-have in #474; raw
   device string is enough for GO.
