# Branching and `main`

The default branch **`main`** is often **protected** on GitHub: **direct pushes are blocked**; changes land via **pull request** (and usually squash merge). Treat **`main` as read-only** in day-to-day work unless you are explicitly performing a maintainer merge.

## Recommended workflow

1. Update local `main`: `git fetch origin` and `git switch main && git pull origin main` (or create a branch from latest `origin/main`).
2. Create a **feature branch**: `git switch -c <branch-name>`.
3. Commit and push: `git push -u origin <branch-name>`.
4. Open a **pull request** into `main` and merge when CI and review are ready.

For **parallel work** (stable PR branch + spike), prefer **git worktrees** — see **`AGENTS.md`**.

## Agents

- **Do not push to `main`** unless the user clearly states that branch protection is waived for that operation.
- For documentation-only or small fixes, still use a **named branch** and a PR unless told otherwise.
