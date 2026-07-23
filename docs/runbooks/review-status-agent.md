# Runbook: review-status agent

Status: Active
Owner: Maintainer + active agents

A polling agent that watches open PRs, makes sure every expected reviewer has
actually run, and — the part that was missing — **routes findings back to the
agent that owns the work**. It does not fix code itself; it collects, triages,
dispatches, and gates.

Source of truth (do not duplicate — reference):
- `AGENTS.md` → *Review Cadence* (trigger intent, close-out routine)
- `docs/decisions/agent-review-contract.md` (severity → who may fix what)
- `docs/skills/rabbit-loop.md` (merge gate)
- `docs/contributing/agent-task-handover-prompt.md` (handoff packet format)

## Why the old instruction was not enough

The previous instruction ("check the PRs for review comments; get CodeRabbit to
answer if rate-limited") is one-directional. Two gaps:

1. **It reads "no comments" as "clean."** That is also true when a reviewer has
   not run yet — the fail-open that merged PR #430 seconds after Qodo first posted.
2. **It never routes.** When comments exist, nothing hands them to the executor
   that owns the branch, so findings sit unactioned.

## The loop (per open PR)

### 1. Collect
Read submitted reviews, inline review comments, and unresolved review threads
(bot and human). Record author, `file:line`, severity, and body.

### 2. Completeness gate — never treat "0 comments" as "reviewed"
For each **expected** reviewer — CodeRabbit, the Cursor bot, and Qodo while it
still exists — confirm it actually ran **since the last commit**. A PR with zero
threads because a reviewer never ran is **not** reviewed.

If CodeRabbit posted "Review limit reached", or has no review after the latest
push, re-trigger **intentionally** (one trigger per stable batch — see the
misclick/rate-limit incident notes):
- `@coderabbitai full review` — no prior CodeRabbit review, or history diverged /
  was force-pushed (a complete pass).
- `@coderabbitai review` — incremental pass after new commits since the last review.

Wait for the reviewer to finish before calling the PR green. **Green needs every
expected bot to have completed**, not just an absence of open threads.

### 3. Triage
Classify each unresolved finding by severity using `agent-review-contract.md`
(Critical / High / Medium / Low; ≤5 tracked files for Medium; escalate Critical,
security, deps, CI, release semantics, and the NEEDS_HUMAN paths).

### 4. Route — the step that was missing
For each PR with open findings, build **one** handoff packet and **dispatch** it
to the executor that owns the work (do not merely log it):

- **Owner** = the agent/session working the PR's `task/*` branch. Fall back to the
  **human** for Critical/security findings, or when the branch has no owning agent.
- **Packet** (per `agent-task-handover-prompt.md`): PR #, branch, base; and per
  finding: `file:line`, severity, one-line problem, the reviewer's suggested fix;
  plus the in-contract bounds ("fix only these files; escalate X").
- **Dispatch**: hand the packet to that executor through whatever mechanism the
  setup uses — spawn a scoped task, message the owning session, or post a scoped
  PR comment. One reliable dispatch is to **@-mention an agent bot on the PR**:
  `@jules` works well for handing a bounded fix to Google Jules (its account logs
  in as `google-labs-jules[bot]`, so match that login when collecting its replies).
  `@coderabbitai` can apply small autofixes the same way. Then reply in each routed
  thread: `Routed to <executor> for fix.`

Routing key = **branch owner** (who) + **file area** (what the contract allows).

### 5. Close-out
Per `AGENTS.md` review close-out, every thread must end with one of:
- `Addressed in <sha>: <what changed>` (Fixed)
- `Not applicable — <reason>` (pre-existing / accepted trade-off / misread)
- `Needs maintainer decision — <why>` (Escalated)

then be resolved. Never silently resolve a thread.

### 6. Merge gate
Never report a PR mergeable while unresolved threads remain **or** no independent
review has landed. Run `scripts/rabbit_loop.sh --merge-gate --pr N`; `CLEAR` only,
otherwise `BLOCKED`.

### 7. Output
One line per PR: `reviewers-run? | unresolved | findings by severity | routed-to | blocker`.

## Worked example — PR #435 (Sentinel: Enforce HTTPS for Jira)

- **Collect / completeness**: CodeRabbit ✓ and Cursor bot ✓ both ran (no rate
  limit) — no re-trigger needed.
- **Triage**: 1 × Major / Security on `collectors/jira.py:177` — auth headers added
  via `add_header` persist across an HTTP redirect (can leak to a downgraded URL).
- **Route**: packet → the agent owning `task/sentinel-jira-https-…`: "fix the
  redirect-header leak within contract bounds; this is security → maintainer nod
  before merge." Reply in the thread: `Routed to <executor> for fix.`
- **Merge gate**: `BLOCKED` (1 unresolved thread) → not mergeable.

Output line:
`#435 | CodeRabbit✓ Cursor✓ | 1 unresolved | 1 Major/security | routed:task-owner+maintainer | BLOCKED(thread)`
