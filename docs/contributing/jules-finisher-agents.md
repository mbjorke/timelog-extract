# Finisher agents for Jules PRs (Cursor or Claude)

Status: **disabled — do not re-enable until a step here can identify a Jules PR**  
Last updated: 2026-08-05

> ## ⚠️ Nothing in this document identifies a Jules PR
>
> The scheduled finisher was switched off in the Jules UI on 2026-08-05 after it
> began modifying Claude-authored pull requests. The cause is not a broken
> `author_gate()` — that function does its job correctly. It is that **no step
> here distinguishes one agent from another**, and two separate instructions
> below assume one does.
>
> ### `author_gate()` answers a different question
>
> `scripts/rabbit_loop.sh::author_gate` checks *internal vs external*: it
> rejects forks and allows an allowlist, `GITTAN_INTERNAL_AUTHORS` defaulting to
> `mbjorke google-labs-jules[bot]`. That is a security boundary against outside
> contributors and it works. It is **not** an "is this Jules" test, and it was
> never written as one.
>
> ### The PR author field cannot tell the agents apart
>
> Every pull request on this repo — Jules, Cursor, Claude and hand-written alike
> — reports `author.login = mbjorke`, because all of them push through the
> maintainer's credentials. So `author_gate()` returns `INTERNAL` for all of
> them, which is correct and also useless for routing.
>
> Two instructions below read that field as if it were an agent marker, and both
> fail — in opposite directions:
>
> - *"if PR author is not `google-labs-jules[bot]`, comment 'not a Jules PR —
>   skipping' and exit"* (Automation instructions) — taken literally, this skips
>   **every** PR, including the Jules ones it exists to process.
> - *"Confirm this PR is from `google-labs-jules[bot]` (or a Jules task branch)"*
>   (both finisher prompts) — the parenthetical is the escape hatch an agent
>   actually takes, and it is far too loose. `task/*` is shared with Cursor and
>   maintainer work (`task/capture-cursor-and-device-labels` is hand-written).
>   This is the reading that let the finisher touch Claude's PRs.
>
> ### Commit authorship *does* distinguish them
>
> Unlike the PR author field, commit authorship is reliable. Surveyed across all
> open PRs on 2026-08-05:
>
> | Agent | Commit author |
> | --- | --- |
> | Jules | `google-labs-jules[bot]` |
> | Cursor | `Cursor Agent` |
> | Claude | `Claude <noreply@anthropic.com>` |
>
> One caveat that decides the rule's shape: branches are **not** single-author
> once anyone helps. Five open PRs currently carry both `Claude` and
> `google-labs-jules[bot]` commits, because Claude pushed review fixes onto
> Jules branches. So:
>
> - *any* commit by Jules → too loose; matches every branch Claude co-authored.
> - **all** commits by Jules → correct, and correctly excludes the mixed
>   branches. A branch another agent or a human has touched is exactly the case
>   that should go to a person, not to an auto-merger.
>
> ### Before re-enabling
>
> Replace every "is this a Jules PR" step with a check on commit authorship —
> *all* commits in `main..HEAD` authored by `google-labs-jules[bot]` — or with a
> dedicated label applied by a trusted workflow. Keep `author_gate()` as-is: it
> is the fork boundary and remains necessary, just not sufficient. Until then
> the personas hand off to a human, see
> [`jules-personas/shared-rules.md`](jules-personas/shared-rules.md).

## Dress rehearsal

This document’s first merge to `main` is the SAFE finisher dress rehearsal: docs / `.jules` learnings only (no collectors or report engine). After CI is green, comment `Ready to merge.` and invoke Cursor §A or Claude `@claude` §B (or add `DRY RUN ONLY` first).

Jules (Bolt / Palette) often **cannot** run `gh` or merge under branch
protection. After review comments are addressed it should hand off (see
[`jules-standing-instructions.md`](jules-standing-instructions.md) §5). A
**finisher** agent with GitHub write access then runs the kanin merge gate and
merges only the safe class.

Pick **Cursor cloud** or **Claude GitHub** based on which quota/credits you have
left that day. Same rules either way.

> **Canonical identifiers in this doc.** The handles and slug below are the real,
> canonical operational values for *this* setup — substitute your own when
> adapting:
> - `google-labs-jules[bot]` — the Jules bot's **commit** author handle (not a
>   placeholder). Match it against commit authorship, never against the PR
>   author field, which is `mbjorke` for every agent on this repo.
> - `OWNER/REPO` = `mbjorke/timelog-extract` — this repository.
> - `@cursor` / `@claude` — the mention handles that actually trigger each
>   finisher; they are commands you type, not example names.

## Shared merge rules (both finishers)

Run from repo root on the Jules PR number `N`:

```bash
scripts/rabbit_loop.sh --agent-gate --pr N
# run on the PR head checkout. Must print AGENT_GATE: google-labs-jules[bot] —
# any other author, or more than one, BLOCKS. This is the agent boundary.

scripts/rabbit_loop.sh --author-gate --pr N
# must print AUTHOR_GATE: INTERNAL — fork/external/unlisted authors BLOCK.
# This is the fork boundary; it does NOT identify which agent wrote the branch.

scripts/rabbit_loop.sh --merge-gate --pr N
# runs author-gate first; must print MERGE_GATE: CLEAR — else reply/resolve threads and stop

scripts/rabbit_loop.sh --classify-merge --pr N
# runs author-gate first; MERGE_CLASS: SAFE → squash-merge allowed
# MERGE_CLASS: NEEDS_HUMAN → do NOT merge; comment + leave for maintainer
#   (optional: scripts/rabbit_handoff.sh --issue <linked-issue>)
```

Only merge when:

1. `AGENT_GATE: google-labs-jules[bot]` (every commit is Jules'; a branch another
   agent or a human has touched goes to a person).
2. `AUTHOR_GATE: INTERNAL` (verified internal author on this repo, not a fork).
3. PR body or a comment contains **ready to merge** / label `jules-merge-ready` (optional but preferred).
4. CI green on the tip.
5. `MERGE_GATE: CLEAR`.
6. `MERGE_CLASS: SAFE`.
7. Diff does **not** delete files that still exist on `origin/main` (stale-tip wipe check — see #387).

Merge method: **squash**, delete branch when offered.

If any check fails: comment what blocked, do not open a second PR, do not merge.

## A. Cursor cloud / Automation (use Cursor credits)

### Manual (Cloud Agent or `@cursor` on the PR)

Paste on the Jules PR (or start a Cloud Agent with the PR URL):

```text
You are the Jules finisher for this repo (timelog-extract / Gittan).

1. Checkout the PR head. Run from repo root:
   - bash scripts/rabbit_loop.sh --agent-gate --pr <N>    # FIRST — agent boundary
   - bash scripts/rabbit_loop.sh --author-gate --pr <N>   # fork boundary, NOT an agent check
   - bash scripts/run_autotests.sh   # if not already green on CI
   - bash scripts/rabbit_loop.sh --merge-gate --pr <N>
   - bash scripts/rabbit_loop.sh --classify-merge
3. If AGENT_GATE is BLOCKED (not Jules, or more than one author on the branch):
   **stop, do not merge** — someone else has worked here.
   If AUTHOR_GATE is BLOCKED (fork / external / unverified author): **stop, do not
   merge, do not approve** — external contributions require a human. This is a
   code-enforced boundary, not a branch-name heuristic (incident: external fork
   PR #N). If MERGE_GATE is not CLEAR, or MERGE_CLASS is NEEDS_HUMAN: comment
   why and stop.
4. Sanity: `git diff --name-status origin/main...HEAD` must not show unexpected
   deletions of files that exist on origin/main (especially core/, scripts/,
   docs/contributing/, tests/). If it does, sync/fix or stop — do not merge.
5. Only if SAFE + CLEAR + CI green: squash-merge with gh or GitHub MCP and
   delete the branch. Reply on the PR with the merge commit / result.

Never weaken branch protection. Never merge number-engine / collectors billing
paths as SAFE without maintainer (classify-merge already flags those).
```

### Automation draft (enable when you want hands-off)

Paste into Cursor Automations (edit scopes/tools in the UI):

| Field | Value |
| --- | --- |
| **Name** | Jules finisher (SAFE merge) |
| **Description** | After Jules marks a PR ready, run merge-gate + classify; squash-merge only SAFE |
| **Trigger** | **Must be scoped to Jules PRs — and the PR author field cannot do that scoping here** (every PR on this repo reports `mbjorke`). Prefer: CI completed success, with the agent check done in the instructions as a commit-authorship test. If the product also allows comment/label triggers, never use “any PR comment contains `ready to merge`” alone. A `jules-merge-ready` label is fine only when the automation still exits immediately unless the commit-authorship test passes. |
| **Repo scope** | `mbjorke/timelog-extract` (this repo only) |
| **Tools** | Shell / repo checkout, GitHub comment, approve (optional), GitHub MCP or `gh` with merge permission |
| **Instructions** | **First step (hard stop):** on the PR head checkout, run `bash scripts/rabbit_loop.sh --agent-gate --pr <N>`. Unless it prints `AGENT_GATE: google-labs-jules[bot]`, comment “not a Jules-only branch — skipping” and exit. Do **not** test the PR author field; it is `mbjorke` for Jules, Cursor and Claude alike, so it passes everything. Then use the **Manual** prompt above. Prefer approve + GitHub auto-merge if direct merge is blocked; never bypass protection. |
| **To finish in editor** | Do **not** wire a PR-author filter into the trigger — no value of it separates Jules from Cursor or Claude on this repo, so it either passes everything or nothing. Scope the trigger as narrowly as the UI allows (repo + CI success), and rely on the commit-authorship hard stop in **Instructions** as the real boundary; it runs on a checkout, which a trigger filter cannot. A Jules-only label applied by a trusted workflow is the one trigger-level filter that would hold. Attach GitHub MCP or secrets for `gh`; enable only if branch protection allows the Cursor actor to merge/approve |

Safer variant: Automation only **approves** + enables GitHub **auto-merge**; GitHub completes the squash when required checks pass. Finisher still must have run merge-gate in the prompt before approving.

## B. Claude Code on GitHub (use Anthropic / Claude credits)

### One-shot: comment on the Jules PR

```text
@claude Finish this Jules PR as the Gittan finisher.

Follow docs/contributing/jules-finisher-agents.md (Shared merge rules).

Steps:
1. On the PR head, run:
   bash scripts/rabbit_loop.sh --agent-gate --pr <this-PR-number>
   bash scripts/rabbit_loop.sh --author-gate --pr <this-PR-number>
   bash scripts/cli_impact_smoke.sh
   bash scripts/run_autotests.sh
   bash scripts/rabbit_loop.sh --merge-gate --pr <this-PR-number>
   bash scripts/rabbit_loop.sh --classify-merge --pr <this-PR-number>
3. If AGENT_GATE is BLOCKED, or AUTHOR_GATE is BLOCKED, or MERGE_GATE is not CLEAR, or MERGE_CLASS is not SAFE: comment the blocker and stop. Do not merge.
4. Check for stale-tip wipes vs origin/main (unexpected deletions). If found, stop.
5. If SAFE + CLEAR + CI green: `gh pr merge <N> --squash --delete-branch`.
6. Comment the result on the PR.

Do not open a new PR. Do not edit .github/ workflows or branch rules.
```

Requires [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions.md)
(`anthropics/claude-code-action`) installed on the repo with a token that can
merge (or approve + auto-merge). Default Claude Action behavior is **not** to
merge — the prompt above is what grants the finisher role.

### Optional workflow sketch

If you add a workflow later, keep it thin: trigger on
`issue_comment` / label `jules-merge-ready`, checkout PR head, run merge-gate +
classify-merge, then `gh pr merge` only on SAFE+CLEAR. Put `.github/` behind
CODEOWNERS so the agent cannot weaken its own gate.

## Jules handoff line (what Jules should post)

When Jules cannot merge itself, one comment is enough:

```text
Ready to merge.

- Review threads addressed (Qodo / CodeRabbit / human).
- CI green on tip.
- Finisher: run docs/contributing/jules-finisher-agents.md (Cursor or @claude).
```

Optional: add label `jules-merge-ready`.

## Credit routing

| You have credits on… | Invoke |
| --- | --- |
| Cursor | Cloud Agent / `@cursor` with §A prompt, or enable the Automation |
| Claude | `@claude` with §B prompt on the PR |
| Neither | Maintainer: same Shared merge rules locally, then `gh pr merge` |

Local Cursor/Claude chat with `gh` remains the lowest-ceremony path when you are
already in the repo.
