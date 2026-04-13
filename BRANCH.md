# Branching and `main`

The default branch **`main`** is **branch-protected** on GitHub: **direct pushes are blocked**; changes land via **pull request** (usually squash merge). **CI** runs on PRs (see **`docs/CI.md`**). Treat **`main` as read-only** unless you are explicitly performing an allowed maintainer merge.

## Recommended workflow

1. Update local `main`: `git fetch origin` and `git switch main && git pull origin main` (or create a branch from latest `origin/main`).
2. Create a branch from that tip:
   - **Release-bound work** (version bumps, changelog cut, PyPI/ship checklist): prefer **`release/X.Y.Z`**, e.g. `git switch -c release/0.2.3`.
   - **Small ad-hoc fixes** may use another clear name; avoid long-lived `feat/…` branches when the goal is a **numbered release** — use `release/X.Y.Z` instead so PR scope matches what merges to `main` for that tag.
3. **Before editing `pyproject.toml` / `CHANGELOG.md` for a release:** confirm you are on the intended branch (`git branch --show-current`); bumps belong on the **`release/*`** (or explicitly agreed) branch for that version, not mixed across versions.
4. Commit and push: `git push -u origin <branch-name>`.
5. Open a **pull request** into `main` and merge when CI and review are ready.

### Squash merge and a second PR from the same `release/*` branch

If you **squash-merge** into `main`, the release branch’s **old commits are not replayed** on `main`—only one squashed commit appears there. Pushing **more commits** to the same `release/X.Y.Z` and opening **another** PR can produce **merge conflicts** (often `CHANGELOG.md` / `README.md`). **Maintainers** do not need to fix that by hand: ask the agent (or run `git fetch origin && git merge origin/main` on the branch, resolve, push). Details: **`docs/VERSIONING.md`** (section *After squash merge*) and **`AGENTS.md`** (releases).

For **parallel work** (stable PR branch + spike), prefer **git worktrees** — see **`AGENTS.md`**.

## Agents

- **Do not push to `main`** — it is protected; use a branch and PR (or the user must explicitly confirm a different process).
- For documentation-only or small fixes, still use a **named branch** and a PR unless told otherwise.
- For **version bumps and release packaging**, prefer a **`release/X.Y.Z`** branch and verify the branch name matches the version being bumped (see **`AGENTS.md`**).
- When the maintainer asks for a **new release**, follow **`AGENTS.md`** (*Releases: what the maintainer means vs what the agent does*) and **`docs/VERSIONING.md`** (*Release workflow: maintainer vs agent*).
