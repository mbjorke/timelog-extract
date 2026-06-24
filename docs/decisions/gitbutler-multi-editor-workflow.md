# GitButler + multi-editor agent workflow

Status: active guidance (maintainer workflow)

## Purpose

This repository is edited with **multiple AI clients** (often **Claude Code** for large
starts, **Cursor** to continue when context/tokens run out) and sometimes **GitButler**
for local branch organization. Without explicit rules, agents step on each other:
stale virtual branches, mixed `git`/`but` writes, and PRs that bundle unrelated scope.

This document is the **repo contract** for that workflow. CLI mechanics live in the
GitButler skill (`but diff`, `--changes`, `but pull`, etc.); this file covers
**when**, **who**, and **handoff**.

Canonical branch/PR policy remains `AGENTS.md` (`task/*` → PR → `main`).

## Maintainer pattern (Claude → Cursor handoff)

Typical flow:

1. **Claude Code** starts a larger job on `task/<scope>` (plain git or GitButler).
2. Work continues until tokens/context limit or session end.
3. **Cursor** picks up the **same** `task/<scope>` branch (or the same GitButler
   virtual branch) and finishes tests, CodeRabbit, push, PR.

Handoff is **branch continuity**, not “two agents inventing parallel truth.”

### Handoff checklist (human or agent, start of every continuation session)

1. **Read ground truth first**
   - Plain git: `git branch --show-current`, `git status -sb`, `git log -3 --oneline`
   - GitButler: `but status -fv` (only if on `gitbutler/workspace`)
   - GitHub: open PR for this branch if it exists (`gh pr view --head <branch>`)
2. **Do not trust the previous chat** — trust branch state + PR thread.
3. **One active intent** on the branch; split unrelated work to a new `task/*`.
4. **Before push:** `bash scripts/run_autotests.sh` (see `.cursor/rules/pre-push-quality-gate.mdc`).
5. **Leave a one-line handoff** in the PR or thread: branch, last commit SHA, what's left.

### What the outgoing editor should leave behind

- All work **committed** (git or `but`) — not only dirty files.
- Branch name matches repo policy: `task/<scope>`.
- If using GitButler: **at most one other virtual branch** applied; prefer only the
  active task branch after `but pull`.
- Short note: done / blocked / next step (PR URL if open).

### What the incoming editor must not do

- Re-run `but setup` or recreate branches without reading current workspace.
- `git checkout` away from an in-progress GitButler session without `but teardown`
  or explicit maintainer OK.
- Merge unrelated fixes into the same branch “while we're here.”
- Push without checking whether another agent already opened a PR for the branch.

## Two modes: plain git vs GitButler

Pick **one mode per clone per work period**. Mixing causes the failures seen in
2026-06-23 sessions (stale stacks, ghost PR branches, `pyproject.toml` merge fights).

| Mode | When | Writes | End session |
| --- | --- | --- | --- |
| **Plain git** | Single agent, simple `task/*` → PR; GitHub is enough | `git` + `gh` | Stay on branch or switch freely |
| **GitButler** | Parallel slices, file-level assignment, local stack try-out | **`but` only** (no `git commit` / `git checkout` / `git merge`) | `but pull` after upstream merges; optional `but teardown` when done |

`but setup` is **not** a daily reinstall — it **re-enters** GitButler mode after
`but teardown`. Project metadata persists under `.git/gitbutler/`.

Reference: [GitButler parallel agents](https://docs.gitbutler.com/ai-agents/parallel-agents).

## GitButler rules (this repo)

### Workspace hygiene

1. **`but pull --check` then `but pull`** after merges to `main` — integrated branches
   are removed automatically; target advances.
2. **Max 1–2 applied virtual branches** that are not yet on GitHub. Remove or
   unapply branches whose PRs already merged.
3. **Do not `but apply` old GitHub PR branches** for integration testing unless
   rebased onto current `main` and scoped intentionally.
4. **Shared hot files** (`pyproject.toml`, `CHANGELOG.md`, `CONTRIBUTING.md`,
   `core/cli_doctor_sources_projects.py`): only one active virtual branch should
   touch them. If two tasks need them, **stack** (`but move child parent`) or
   **sequential** PRs — not parallel apply.

### Commit conflict workaround (observed)

When commit fails because multiple stacks touch the same file:

```text
but unapply <other-branch>   # repeat until only active branch + upstream
but commit <branch> -m "..." --changes <ids>
but apply <other-branch>   # only if still needed
```

Prefer **`but diff` → `but commit … --changes`** over path-based guesses.

### Parallel agents (Cursor + Claude, or two Cursor sessions)

Aligned with GitButler docs and multi-agent practice:

- **Independent tasks** → separate virtual branches (`task/foo`, `task/bar`).
- **Dependent task** → stack explicitly: `but move task/frontend task/backend`.
- **Same file overlap** → call out before commit; unapply, stack, or use a **git worktree**
  (e.g. `timelog-extract-toggl` for isolated long-running work).
- **One clone = coordinate** — two editors without `but pull`/handoff will diverge.

GitButler parallel branches share **one filesystem** — not runtime isolation. Use
**worktrees** when dependencies, servers, or competing edits need separation.

### PR boundary (unchanged)

GitButler organizes **local** work. **PR / review / merge** stay on GitHub:

```text
but push task/<scope>     # or but pr new <branch-id>
gh pr create / update     # if not using but pr new
merge on GitHub → but pull
```

One virtual branch → one PR when scopes are independent.

## Editor-specific notes

| Editor | Guidance |
| --- | --- |
| **Claude Code** | Good for large exploration; commit before handoff; optional hooks: `but claude post-tool` (see GitButler AI docs). |
| **Cursor** | Read `.cursor/rules/gitbutler-multi-editor-workflow.mdc`; run tests in session; use `gh` for PR threads. |
| **Both on same branch** | Same handoff checklist; never assume the other tool ran `but pull`. |

Personal GitButler CLI skill (install locally; operational `but` command detail) lives outside this repo — see upstream GitButler docs and your editor’s skill path. Do not duplicate that skill here; this doc is **policy** only.

## When to choose worktrees instead

Use `./scripts/git_worktree.sh` or a sibling clone when:

- Two agents need **incompatible** checkouts or long-running dev servers.
- Same files would be edited concurrently with no coordination window.
- A spike must not disturb an open PR branch in the primary tree.

GitButler and worktrees can coexist: **But in primary clone**, plain git in worktrees.

## Anti-patterns (learned 2026-06-23)

| Anti-pattern | Result |
| --- | --- |
| Stack 5+ merged `task/*` branches in one workspace | `pyproject.toml` / CHANGELOG merge conflicts on commit |
| Agent merges PRs with `gh` while GitButler workspace stale | Ghost branches, wrong base SHA |
| `#166`-style bundle (spinner + chrome + …) in one PR | Review/merge pain; split virtual branches early |
| Cursor “Create PR” while PR already exists | Duplicate PR confusion — check `gh pr list` |
| Second agent continues without reading branch state | Duplicate commits (`cd04aa2` vs rebased `3ab5ddf`) |

## See also

- [`AGENTS.md`](../../AGENTS.md) — branch policy, test gate, review close-out
- [`docs/contributing/ai-assisted-work.md`](../contributing/ai-assisted-work.md) — tool matrix
- [`docs/decisions/agent-focus-workflow.md`](agent-focus-workflow.md) — intent / scope / verify
- [`BRANCH.md`](../../BRANCH.md) — `task/*` → `main`
- [GitButler parallel agents](https://docs.gitbutler.com/ai-agents/parallel-agents)
