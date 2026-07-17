# Finisher agents for Jules PRs (Cursor or Claude)

Status: active  
Last updated: 2026-07-17

## Dress rehearsal

This document’s first merge to `main` is the SAFE finisher dress rehearsal: docs / `.jules` learnings only (no collectors or report engine). After CI is green, comment `Ready to merge.` and invoke Cursor §A or Claude `@claude` §B (or add `DRY RUN ONLY` first).

Jules (Bolt / Palette) often **cannot** run `gh` or merge under branch
protection. After review comments are addressed it should hand off (see
[`jules-standing-instructions.md`](jules-standing-instructions.md) §5). A
**finisher** agent with GitHub write access then runs the kanin merge gate and
merges only the safe class.

Pick **Cursor cloud** or **Claude GitHub** based on which quota/credits you have
left that day. Same rules either way.

## Shared merge rules (both finishers)

Run from repo root on the Jules PR number `N`:

```bash
scripts/rabbit_loop.sh --merge-gate --pr N
# must print MERGE_GATE: CLEAR — else reply/resolve threads and stop

scripts/rabbit_loop.sh --classify-merge
# MERGE_CLASS: SAFE → squash-merge allowed
# MERGE_CLASS: NEEDS_HUMAN → do NOT merge; comment + leave for maintainer
#   (optional: scripts/rabbit_handoff.sh --issue <linked-issue>)
```

Only merge when:

1. Author is `google-labs-jules[bot]` (or head branch clearly Jules/`task/…` from a Jules brief).
2. PR body or a comment contains **ready to merge** / label `jules-merge-ready` (optional but preferred).
3. CI green on the tip.
4. `MERGE_GATE: CLEAR`.
5. `MERGE_CLASS: SAFE`.
6. Diff does **not** delete files that still exist on `origin/main` (stale-tip wipe check — see #387).

Merge method: **squash**, delete branch when offered.

If any check fails: comment what blocked, do not open a second PR, do not merge.

## A. Cursor cloud / Automation (use Cursor credits)

### Manual (Cloud Agent or `@cursor` on the PR)

Paste on the Jules PR (or start a Cloud Agent with the PR URL):

```text
You are the Jules finisher for this repo (timelog-extract / Gittan).

1. Confirm this PR is from google-labs-jules[bot] (or a Jules task branch).
2. Checkout the PR head. Run from repo root:
   - bash scripts/run_autotests.sh   # if not already green on CI
   - bash scripts/rabbit_loop.sh --merge-gate --pr <N>
   - bash scripts/rabbit_loop.sh --classify-merge
3. If MERGE_GATE is not CLEAR, or MERGE_CLASS is NEEDS_HUMAN: comment why and stop.
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
| **Trigger** | **Must be scoped to Jules PRs.** Prefer: CI completed success **and** author is `google-labs-jules[bot]`. If the product also allows comment/label triggers, combine with an author filter — never “any PR comment contains `ready to merge`” alone. Label `jules-merge-ready` is fine only when the automation still exits immediately unless the PR author is Jules. |
| **Repo scope** | `mbjorke/timelog-extract` (this repo only) |
| **Tools** | Shell / repo checkout, GitHub comment, approve (optional), GitHub MCP or `gh` with merge permission |
| **Instructions** | **First step (hard stop):** if PR author is not `google-labs-jules[bot]`, comment “not a Jules PR — skipping” and exit. Then use the **Manual** prompt above. Prefer approve + GitHub auto-merge if direct merge is blocked; never bypass protection. |
| **To finish in editor** | Wire the Jules-author filter into the trigger if the UI supports it. If the UI **cannot** filter by author, do **not** enable broad comment/label triggers — keep hands-off automation disabled and finish manually (or use a Jules-only label applied by a trusted workflow); the hard-stop first step is defense in depth, not the trigger scope. Attach GitHub MCP or secrets for `gh`; enable only if branch protection allows the Cursor actor to merge/approve |

Safer variant: Automation only **approves** + enables GitHub **auto-merge**; GitHub completes the squash when required checks pass. Finisher still must have run merge-gate in the prompt before approving.

## B. Claude Code on GitHub (use Anthropic / Claude credits)

### One-shot: comment on the Jules PR

```text
@claude Finish this Jules PR as the Gittan finisher.

Follow docs/contributing/jules-finisher-agents.md (Shared merge rules).

Steps:
1. Verify author is google-labs-jules[bot] (or Jules task branch).
2. On the PR head, run:
   bash scripts/rabbit_loop.sh --merge-gate --pr <this-PR-number>
   bash scripts/rabbit_loop.sh --classify-merge
3. If not CLEAR or not SAFE: comment the blocker and stop. Do not merge.
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
