# Runbook: review-status agent

Status: Active
Owner: Maintainer + active agents

A polling agent that watches open PRs, makes sure every expected reviewer has
actually run, and — the part that was missing — **routes findings back to the
agent that owns the work**. It does not fix code itself; it collects, triages,
dispatches, and gates.

**Hard rule — router, not executor.** This agent NEVER edits code, commits, opens
a PR, or spawns a coding/background agent to perform a fix. Its only side effect is
posting routing comments (and, at most, assigning or labelling). If an instruction
says "spawn a task" or "dispatch", that means *post a hand-off comment* — not run
the work itself. An agentic runner (e.g. a Cursor composer agent) will otherwise
read "spawn" as "go fix it" and emit a commit — which is a bug here, and produces
duplicate work against the executor you routed to.

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
For each **expected** reviewer — CodeRabbit (free) and the Cursor bot — confirm it
actually ran **since the last commit**. A PR with zero threads because a reviewer
never ran is **not** reviewed. (Qodo's trial ended 2026-07-23 and won't be paid
for, so the rule is now "CodeRabbit + one independent cross-check" — the Cursor
bot, or `/gittan-review` run as a separate process — not "two external bots".)

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
- **One executor per finding — never broadcast.** If the `task/*` branch already
  has an active agent committing to it, route there and to no one else. Do **not**
  also @-mention a second agent for the same finding: two agents on one fix produce
  duplicate, conflicting commits (observed on #435 — a Cursor agent and Jules both
  fixed the same finding).
- **Dispatch = one PR comment, nothing else.** Post ONE comment with the packet,
  addressed to the chosen executor. Do **not** spawn a task or agent to perform the
  fix — comment / @-mention (or assignment) only. Then reply in each thread:
  `Routed to <executor>.`
- **Mention identity matters.** Agent bots (Jules included) ignore @-mentions
  authored by *other bots* — loop-prevention. If this agent posts as a bot account,
  an `@jules` mention will **not** trigger Jules (same text from a human does). So
  post the routing comment under a **human / PAT identity**, or trigger Jules via
  **assignment / label** instead of a bot mention. (`@jules` → account
  `google-labs-jules[bot]`; match that login when collecting its replies.)

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

**Green CI is not proof the fix survived.** When two agents touched the same PR,
one can revert the other's fix while tests stay green (the tests that would catch
it were moved or only cover the weaker condition). Before calling a
security/correctness PR done, diff the actual fix artifact across commits to
confirm the guard is still there — do not trust an agent's "all passing cleanly".
(Regression: on #435 a Jules "relocate tests" commit dropped a restored redirect
guard behind green tests.) Enforce one executor per finding (step 4).

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
