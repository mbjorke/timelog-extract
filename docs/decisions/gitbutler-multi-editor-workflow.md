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

A **primary maintainer use case** for GitButler in this repo: work on **many
`task/*` features in parallel** (separate virtual branches, selective commits) and
**test one feature at a time** without `git checkout` or a worktree per feature.
See [Parallel development + isolated testing](#parallel-development--isolated-testing).

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
- If using GitButler: active task branch **applied**; other features may stay **unapplied**
  (parked). Prefer **one applied stack** when handing off to an agent unless integration
  testing of two file-disjoint slices was explicitly in progress.
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
| **GitButler** | Many features in parallel; file-level assignment; test via apply/unapply without checkout | **`but` only** (no `git commit` / `git checkout` / `git merge`) | `but pull` after upstream merges; optional `but teardown` when done |

`but setup` is **not** a daily reinstall — it **re-enters** GitButler mode after
`but teardown`. Project metadata persists under `.git/gitbutler/`.

Reference: [GitButler parallel agents](https://docs.gitbutler.com/ai-agents/parallel-agents).

## GitButler rules (this repo)

### Parallel development + isolated testing

**Goal:** many features in flight, but run tests against **one feature (or one intentional
combo)** without worktree hopping.

**What GitButler gives you**

| Capability | Mechanism |
| --- | --- |
| Parallel **organisation** | Many virtual branches; assign files/hunks per lane; commit slices with `--changes` |
| Parallel **parking** | Unapplied branches hold WIP commits off the working tree |
| Isolated **testing** | Control what is **applied** — working tree = union of applied stacks only |
| Lighter than checkout | `but apply` / `but unapply` reuses one clone, one `.venv`, one editable install |

**What GitButler does not give you**

- Two features **running tests at the same time** in the same tree (still one filesystem).
- Isolation when two applied stacks touch the **same hot file** — use stack, sequential apply, or a worktree.
- A substitute for worktrees when you need **two long-running processes** (servers, spikes).

**Operating modes**

| Mode | Applied stacks | When |
| --- | --- | --- |
| **Focus + test** | **1** (the feature under test) | Default — `bash scripts/run_autotests.sh`, push prep |
| **Integration probe** | **2**, file-disjoint only | “Do A + B work together before PR?” |
| **Parked WIP** | **0–1** + many **unapplied** branches | Commits saved; tree stays clean for the active slice |

Many **unapplied** branches in `but branch list` is normal and desired. The limit is on
**applied** stacks at test time, not on how many features you track.

**Test another feature (template)**

```bash
but oplog snapshot -m "before try task/feature-x"
but unapply task/current-feature          # if applied
but apply task/feature-x
bash scripts/run_autotests.sh             # or a targeted unittest / CLI smoke
but unapply task/feature-x
but apply task/current-feature            # restore focus
```

Unassigned changes in `zz` usually persist across apply/unapply — commit or stage them
to the active branch before switching if apply warns about overwritten files.

**When worktrees still win**

- Same hot file edited in two features **concurrently** (not “test one, then the other”).
- Two terminals need **different checkouts at once** (parallel CI repro, extension + CLI spike).
- Incompatible `pyproject.toml` / dependency lines between features.

Primary clone: GitButler for day-to-day parallel features. Worktrees for exceptions
(`./scripts/git_worktree.sh`).

References: [parallel branches](https://docs.gitbutler.com/cli-guides/cli-tutorial/branching-and-commiting#parallel-branches),
[GitButler virtual branches](https://docs.gitbutler.com/features/branch-management/virtual-branches).

### Workspace hygiene

1. **`but pull --check` then `but pull`** after merges to `main` — integrated **applied**
   stacks advance; remove stale lanes per the cleanup runbook.
2. **Applied stacks:** prefer **one** when testing or handing off to an agent; **two** only
   for deliberate integration of file-disjoint slices. **Unapplied** parked branches may
   be many — prune merged/abandoned ones periodically (see runbook).
3. **Do not `but apply` old GitHub PR branches** for integration testing unless
   rebased onto current `main` and scoped intentionally.
4. **Shared hot files** (`pyproject.toml`, `CHANGELOG.md`, `CONTRIBUTING.md`,
   `core/cli_doctor_sources_projects.py`): only one applied virtual branch should
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

### When to use parallel, stack, worktree, or plain git

Use this **before** creating or applying another virtual branch:

```text
One agent, one PR, no file-level slicing needed?
  → plain git on task/<scope>  OR  GitButler with one applied branch

Independent slices, different files, short session, max two lanes?
  → parallel apply (task/foo + task/bar); unapply before commit if hot files overlap

Slice B depends on slice A (B's PR should stack on A's)?
  → stack: but branch new -a task/backend task/frontend
     or: but move task/frontend task/backend

Same hot file OR two dev servers OR long-running spike?
  → git worktree (./scripts/git_worktree.sh), not parallel But in one tree

Finished / merged on GitHub?
  → but pull --check && but pull  (updates applied stacks; does not always drop unapplied lanes)
  → remove stale unapplied branches (see runbook below)
```

References: [parallel branches](https://docs.gitbutler.com/cli-guides/cli-tutorial/branching-and-commiting#parallel-branches),
[stacked branches](https://docs.gitbutler.com/cli-guides/cli-tutorial/branching-and-commiting#stacked-branches).

### Rubbing (`but rub`) — move changes without rebase surgery

[`but rub`](https://docs.gitbutler.com/cli-guides/cli-tutorial/rubbing) moves **files, hunks, or commits**
to a target (branch, commit, or special IDs). Prefer rub over raw `git rebase -i` in But mode.

Special IDs (from `but status -fv`):

| ID | Meaning |
| --- | --- |
| `zz` | Unassigned (working tree / staging lane) |
| branch name or CLI id | Assign changes to that virtual branch |

Common recipes (use IDs from `but diff` or `but status -fv`, never guess paths):

```text
Assign unassigned hunk to branch:     but rub h0 task/foo
Unassign (back to zz):                but rub h0 zz
Amend existing commit:                but rub h0 c3
Squash commit c5 into c3:             but rub c5 c3
Uncommit (changes → zz):              but rub c3 zz
Move commit to another branch:        but rub c3 task/bar
Split a commit:                       but commit empty --after c3
                                      then but rub <file-id> <new-empty-commit-id>
                                      then but reword <commit-id>
```

After any rub that rewrites history: refresh IDs from the printed workspace state before
the next mutation. Do not chain `but` commands with `&&`.

Alternative to rub for stacking only: `but move <child-branch> <parent-branch>` (branch names,
not commit IDs).

## Editor-specific notes

| Editor | Guidance |
| --- | --- |
| **Claude Code** | Good for large exploration; commit before handoff; optional hooks: `but claude post-tool` (see GitButler AI docs). Opt-in helpers: `but commit --ai` / `but squash --ai` generate a message from the staged changes (still run the autotests gate first; reword to match our English, scope-bounded convention). |
| **Cursor** | Read `.cursor/rules/gitbutler-multi-editor-workflow.mdc`; run tests in session; use `gh` for PR threads. |
| **Both on same branch** | Same handoff checklist; never assume the other tool ran `but pull`. |

Personal GitButler CLI skill (install locally; operational `but` command detail) lives outside this repo — see upstream GitButler docs and your editor’s skill path. Do not duplicate that skill here; this doc is **policy** only.

## Keeping GitButler + skill current

`but` releases roughly weekly. It is a **personal, local tool** — not a repo dependency,
not pinned in `pyproject.toml`, not a CI concern. Keeping it current is per-machine
maintenance, not a repo change.

| Task | Command |
| --- | --- |
| Check for a new CLI version | `but update check` |
| Update the CLI | `but update` (or `brew upgrade gitbutler`, or re-run the [installer](https://gitbutler.com/cli)) |
| Refresh the skill after updating | `but skill install --detect` |

- **Update the skill after every GitButler upgrade** — the templates ship with the
  binary and drift otherwise (GitButler docs: *"update the skill after updating
  GitButler"*). Use `but skill install` / `--detect` for **just the skill files**.
- **Avoid `but agent setup` in this repo.** The wizard writes workflow preferences into
  agent instruction files (`AGENTS.md` / `CLAUDE.md`) and can overwrite our curated
  policy. This doc is the policy; run the skill installer, not the wizard.
- **CLI ships with the desktop app.** After a desktop auto-update `but` can break
  (upstream [#12043](https://github.com/gitbutlerapp/gitbutler/issues/12043)); reinstall
  the CLI (global settings → *Install CLI*, or the installer script) if it does.

## When to choose worktrees instead

Use `./scripts/git_worktree.sh` or a sibling clone when:

- Two agents need **incompatible** checkouts or long-running dev servers.
- Same files would be edited concurrently with no coordination window.
- A spike must not disturb an open PR branch in the primary tree.

GitButler and worktrees can coexist: **But in primary clone**, plain git in worktrees.

**Caveat — a fresh worktree has no `.venv`.** The test gate finds Ruff via
`<root>/.venv/bin/ruff` (`scripts/run_lint.sh`, called by `run_autotests.sh`); a new
worktree lacks that env, so lint exits non-zero under `set -e` and the unit tests
never run — which reads as a *test failure*, not a setup gap. Give the worktree an
env before running the gate:

```bash
# from the sibling worktree, reuse the primary clone's env:
ln -sfn ../../<primary-clone>/.venv .venv    # then add .venv to .git/info/exclude
# or create a dedicated one for this worktree:
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'
```

## Anti-patterns (learned 2026-06-23)

| Anti-pattern | Result |
| --- | --- |
| Stack 5+ merged `task/*` branches in one workspace | `pyproject.toml` / CHANGELOG merge conflicts on commit |
| Agent merges PRs with `gh` while GitButler workspace stale | Ghost branches, wrong base SHA |
| `#166`-style bundle (spinner + chrome + …) in one PR | Review/merge pain; split virtual branches early |
| Cursor “Create PR” while PR already exists | Duplicate PR confusion — check `gh pr list` |
| Second agent continues without reading branch state | Duplicate commits (`cd04aa2` vs rebased `3ab5ddf`) |
| `but branch delete task/foo` on an **unapplied** lane | `Could not find branch` — delete only sees **applied** stacks |
| Bulk apply+delete with active branch **unapplied** first | Can flood `zz` with old branch diffs; use snapshot + restore |
| All applied stacks left on during every test | Tests exercise accidental union of A+B+C |
| Expect GitButler to run two isolated test suites simultaneously | Use worktrees or sequential apply/unapply |
| Reuse an existing `task/*` name / branch without checking local lanes first | Branch collision; another agent's commit left dangling — recovered via reflog + `git tag safety/…` (2026-07-02, GH #240/#272) |
| Assume a fresh worktree can run `run_autotests.sh` as-is | Missing `.venv` → Ruff gate fails, tests never run (see caveat above), 2026-07-02 |

## See also

- [`docs/runbooks/gitbutler-workspace-cleanup.md`](../runbooks/gitbutler-workspace-cleanup.md) — branch graveyard cleanup (apply-then-delete)
- [`AGENTS.md`](../../AGENTS.md) — branch policy, test gate, review close-out
- [`docs/contributing/ai-assisted-work.md`](../contributing/ai-assisted-work.md) — tool matrix
- [`docs/decisions/agent-focus-workflow.md`](agent-focus-workflow.md) — intent / scope / verify
- [`BRANCH.md`](../../BRANCH.md) — `task/*` → `main`
- [GitButler parallel agents](https://docs.gitbutler.com/ai-agents/parallel-agents)
