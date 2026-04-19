# Aligning `dev` with `main` (after long divergence)

**When this applies:** Use when a **`dev`** branch **exists** and has **split history** with **`main`** (forks, or if the project reintroduces a second integration line). **Default upstream** workflow is **`task/* → main`** only — see [`BRANCH.md`](../../BRANCH.md).

## Purpose / when to use

Use when `dev` and `main` have **split histories** (many unique commits on each side) and **policy is that `main` is canonical** (releases, PyPI) while `dev` was an integration line that **must not** stay a parallel universe. Branching intent for day-to-day work stays in [`BRANCH.md`](../../BRANCH.md).

**Goal:** get `dev` to the **same tree and forward history as `main`**, with **minimized risk** and a **reversible** breadcrumb. **This runbook is not a substitute** for the maintainer deciding that **no** unique, untransferred work remains on `dev` — re-verify with `git log` / spot diffs on critical paths if uncertain.

## Prerequisites

- **Human decision:** Confirm nothing on `dev` must be cherry-picked to `main` before you discard the divergent `dev` tip (or document what was salvaged).
- **GitHub:** Ability to **push a tag** and, for path **C1**, to **force-push** `dev` (may need a temporary branch-protection exception — see *Protected branches* below).
- **Local clone:** Clean working tree on the machine performing the reset (`git status` shows no unexpected changes).
- **Tests:** After reset, **`bash scripts/run_autotests.sh`** (from **repository root** — same as [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and CI) must pass on the **`main`** tree before you push `dev` (same files as `main` for C1). Prefer `bash scripts/…` over `./scripts/…` so the run does not depend on the executable bit.

> **Protected branches:** Both `dev` and `main` are protected (see [`BRANCH.md`](../../BRANCH.md)). A **force-push** to `dev` may require a temporary rules exception or admin action in GitHub **Branch protection**. Plan that before you promise timing.

## Principles

1. **Never** force to `main`. Alignment is about fixing **`dev`**, not rewriting release history.
2. **Tag first** the current `dev` tip so the old state is recoverable (`archive/dev-…` or a dated name).
3. **Prefer** making `dev` **exactly** `main`’s commit over a 143-file “merge and pray” if product truth already lives on `main`.
4. **Agents (local or cloud):** work from **fetched** `origin`, document **hashes and counts** in the handoff, and do not skip **`bash scripts/run_autotests.sh`** (repo root) on a clone that will become the new integration base after alignment.

## Phase A — Diagnosis (read-only; paste output into the issue/PR for humans)

```bash
git fetch origin
git rev-parse origin/main origin/dev
git merge-base origin/main origin/dev
git rev-list --left-right --count origin/main...origin/dev
# Optional: name-only or stat summary to understand blast radius
git diff --stat origin/main origin/dev | tail -5
```

Interpretation: **right-only** and **left-only** counts on `main...dev` are the asymmetric commit counts. Large **file** diffs are expected if one side had refactors the other did not.

## Phase B — Backup the old `dev` tip (tag on GitHub)

On `origin` (or via `gh`):

- Create an **annotated or lightweight** tag on **current** `origin/dev` before any destructive step, e.g. `archive/dev-YYYY-MM-DD` (use the **actual** date; avoid reusing a tag name).

This gives a **permanent** pointer for archaeology and diff review later.

## Phase C — Chosen path (pick one; default when `main` is canonical: **C1**)

### C1 — Reset `dev` to match `main` (file-identical, cleanest)

*Requires* permission to **update `dev` with a non-fast-forward** push, or a GitHub “replace” workflow your org allows.

Local sequence (illustrative; the maintainer’s machine with credentials). **Run every command from the repository root** (the directory that contains `pyproject.toml` and `scripts/run_autotests.sh`).

```bash
cd /path/to/timelog-extract   # repository root — required

git fetch origin
git switch dev 2>/dev/null || git switch -c dev --track origin/dev
git pull origin dev
git reset --hard origin/main

# CI-parity gate (same as CONTRIBUTING.md / CI python job)
bash scripts/run_autotests.sh

git push origin dev --force-with-lease
```

- **`--force-with-lease`** reduces the risk of clobbering a surprise update to `dev` between fetch and push.
- If **push is rejected** by rules, use **Settings → Branches** to allow a one-time force, or an admin **GitHub Action** (with approval) that performs the reset — *do not* bypass security without the maintainer.

After success: `origin/dev` and `origin/main` should **point to the same commit**; future `task/*` branches can track that tip from **`dev`** (or from **`main`** if you retire `dev`).

#### Verification checklist (after C1 push)

- [ ] `git fetch origin && git rev-parse origin/main origin/dev` — **two identical SHAs**.
- [ ] `git log -1 origin/dev` — message matches the current release line on `main` (e.g. latest release commit).
- [ ] Optional: `git diff origin/main origin/dev` — **empty**.

### C2 — Merge (only if you must *preserve* `dev`’s commit history on the graph)

`git switch dev` → `git merge origin/main` → resolve conflicts. **This does not** guarantee a tree identical to `main`; it guarantees a merge commit. Use only when you explicitly need the old `dev` chain visible — usually **worse** for a badly diverged `dev` that is being retired as a “second line.”

### C3 — New branch and PR (when force is not allowed and you can approximate)

- Branch **`resync/dev-from-main`** from **`origin/main`**, open PR **into** `dev`.
- In **simple** fast-forwardable cases, GitHub can align `dev`; if histories diverge, the merge is still a **normal** merge, not a hard reset. Often **C1** is the real fix; **C3** is a fallback when org policy blocks force and the PR ends up a large merge (high conflict risk). Prefer solving policy for **C1** if the intent is true alignment.

## Rollback (restore `dev` from the archive tag)

If you must **undo** a C1 alignment and put `remote` `dev` back to the pre-alignment commit (the one you tagged):

```bash
cd /path/to/timelog-extract   # repository root

git fetch origin --tags
# Replace TAG with your archive tag, e.g. archive/dev-pre-align-20260418
git switch dev
git pull origin dev   # if needed; or ensure you have latest refs
git reset --hard TAG
bash scripts/run_autotests.sh   # optional but recommended before pushing
git push origin dev --force-with-lease
```

Anyone who based work on the aligned `dev` should **rebase or reset** their branches after a rollback. Document the rollback in the same **issue** you used for alignment.

## Phase D — After alignment

- Post a short **issue or discussion** note: *what* was done (C1/C2/C3), **tag** name of old `dev`, and **date**.
- In [`docs/ideas/til/`](../../ideas/til/) add a **TIL** only for a **genuine** learning that day (see [`til/README.md`](../../ideas/til/README.md)); otherwise note outcomes under [`docs/ideas/`](../../ideas/) or the issue.
- Re-teach **all** open automation: new work should use **`dev` = current `main` tip**; close obsolete PRs that targeted the old `dev` if they are moot.
- For **orchestrated “agent → agent in cloud”** work: paste **Phase A output** and the chosen path into a single GitHub **Issue** or the task prompt [`dev-main-alignment-handoff.md`](../task-prompts/dev-main-alignment-handoff.md) so the next agent is not re-discovering the graph.

## References

- [`AGENTS.md`](../../AGENTS.md) — test gate, branch policy.
- [`BRANCH.md`](../../BRANCH.md) — `task/*` and PR intent.
- [`ci.md`](ci.md) — what CI enforces on PRs.
