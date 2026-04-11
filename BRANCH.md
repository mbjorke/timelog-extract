# Branching and `main`

The default branch **`main`** is **branch-protected** on GitHub: **direct pushes are blocked**; changes land via **pull request** (usually squash merge). **CI** runs on PRs (see **`docs/CI.md`**). Treat **`main` as read-only** unless you are explicitly performing an allowed maintainer merge.

## Recommended workflow

1. Update local `main`: `git fetch origin` and `git switch main && git pull origin main` (or create a branch from latest `origin/main`).
2. Create a **feature branch**: `git switch -c <branch-name>`.
3. Commit and push: `git push -u origin <branch-name>`.
4. Open a **pull request** into `main` and merge when CI and review are ready.

For **parallel work** (stable PR branch + spike), prefer **git worktrees** — see **`AGENTS.md`**.

## Agents

- **Do not push to `main`** — it is protected; use a branch and PR (or the user must explicitly confirm a different process).
- For documentation-only or small fixes, still use a **named branch** and a PR unless told otherwise.
