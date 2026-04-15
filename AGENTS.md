# Agent Rules

## Do not

Hard rules derived from real incidents and orchestration learnings. Each links to the
`docs/til/` entry that produced it.

| # | Do not | Why / reference |
|---|---|---|
| 1 | Fix code during a review task | Record findings in the document; fixes are a separate task → [TIL 2026-04-11](til/2026-04-11-review-tasks-are-documents-not-code.md) |
| 1b | Fix unrelated things when starting an RC | Note them, finish the scoped work, open a separate branch → [TIL 2026-04-11](til/2026-04-11-dont-fix-unrelated-things-in-an-rc.md) · [incident](incidents/2026-04-11-unrelated-fix-bundled-into-review-branch.md) |
| 1c | *(maintainer)* Click CodeRabbit suggestions on an out-of-scope PR | Each click deepens the scope drift; split the branch first → [TIL 2026-04-12](til/2026-04-12-coderabbit-checkbox-as-scope-decision.md) · [incident](incidents/2026-04-12-coderabbit-checkbox-cascade-on-out-of-scope-pr.md) |
| 2 | Invent or round `TIMELOG.md` timestamps | Wrong timestamps corrupt the time record → [incident 2026-04-09](incidents/2026-04-09-timelog-timestamp.md) |
| 3 | Commit `TIMELOG.md` | Gitignored by policy; contains private work data |
| 4 | Commit `timelog_projects.json` | User-owned config, not recoverable from git if lost |
| 5 | Commit anything under `private/` | Local business notes, never version-controlled |
| 6 | Push directly to `main` | Branch-protected; all changes go through a PR |
| 7 | Delete or rename `timelog_projects.json` without confirmation | Only copy; treat as critical data → [TIL 2026-04-13](til/2026-04-13-gitignored-config-is-not-disposable.md) |

---

## Standard Timelog Policy

- Use exactly one local timelog file by default: `<current_repo_root>/TIMELOG.md` (the repository where the command is being run).
- If CLI option `--worklog PATH` is provided, that path overrides the default for that run.
- If `TIMELOG.md` does not exist, create it before logging work.
- Add entries during/after meaningful work using this format:
  - `## YYYY-MM-DD HH:MM`
  - `- <short summary of what was done>`
- **Clock time must be real local wall time** when the entry is written. Do not invent, round to a “nice” hour, or default to placeholder times (for example `18:00`). Wrong timestamps defeat the purpose of the log.
- **How to get the time:** run `date '+%Y-%m-%d %H:%M'` in the repo environment and use that for `YYYY-MM-DD HH:MM`, or use a time the user explicitly stated in the thread. If neither is available, ask the user before appending an entry.
- **Resolution order (for agents):**
  1. If user/command includes `--worklog PATH`, use that path.
  2. Else use `<current_repo_root>/TIMELOG.md`.
  3. If the chosen file does not exist, create it before appending.

## Git Safety

- Never commit `TIMELOG.md`.
- Ensure `TIMELOG.md` remains gitignored.
- If `TIMELOG.md` is accidentally staged, unstage it before commit.
- Do not commit a **`private/`** directory or other gitignored local business notes (see **`docs/PRIVATE_LOCAL_NOTES.md`**).

## Local data safety (destructive commands)

- **Do not use destructive or irreversible shell steps lightly** when they touch user-owned or gitignored state. Examples: `mv` / `rm` on **`timelog_projects.json`**, **`TIMELOG.md`**, dated backups, or anything under **`private/`**.
- Before renaming, moving aside, or deleting files that are the **only copy** of configuration or work history, **confirm with the user** or use a **non-destructive** pattern first (e.g. `cp` to a timestamped path outside the repo, or document exact restore steps).
- Scenario testing and “quick cleanup” are common ways to lose data; treat **`timelog_projects.json`** as **critical** even though it is gitignored.
- **Incident reference** (project config lost during manual matrix scenario work, recovery from git history): **`docs/incidents/2026-04-13-project-config-backup-gap.md`**.

## Task types — read the brief before acting

Before writing a single line of code or prose, identify what type of task you have been given. Delivering the wrong type of output wastes the PR cycle even if the work itself is correct.

### Review

The deliverable is a **document** — an analysis, findings list, or recommendation — committed as a Markdown file on the feature branch. Code changes are **not part of a review task** unless explicitly requested.

Rules:
- Read and analyse first. Write the document. Commit it.
- If you find a bug or security issue while reading, **record it as a finding in the document** with a clear description and recommended fix.
- Do **not** implement the fix during the review pass. Note it, then stop.
- If a finding is critical enough that you believe an immediate fix is warranted, say so in the document and ask the maintainer before touching code.

**Why:** bundling an unasked-for code fix into a review PR muddies the deliverable, makes the PR harder to evaluate as a review, and may cause the whole branch to be set aside even if the fix is correct. The review document is the finish line for a review task.

**Reference incident (April 2026):** `claude/gittan-launch-review-4a5DD` was a review-only task. The agent produced the correct review document but also fixed a security issue in `collectors/chrome.py` in the same commit. Marcus cherry-picked the fix into `main` manually (PR #14), but the branch was never evaluated as a review because its scope was muddled. Fix landed; review did not get a proper cycle.

### Implementation

The deliverable is **working code** — changed files, passing tests, a clean commit on the feature branch. Write the code, run `bash scripts/run_autotests.sh`, fix failures, commit, push.

### Hybrid (review + implementation in the same task)

Only when the brief explicitly asks for both. Use **two separate commits in this order**:
1. The review/analysis document.
2. The code changes, with the commit message referencing the findings from commit 1.

This keeps each deliverable independently reviewable.

## Branch policy (`main`)

- **`main` is branch-protected** (no direct push). Land changes via a **named branch**, push to `origin`, and merge via **pull request**.
- **Prefer release branches** over open-ended `feat/…` names: from latest `origin/main`, create **`release/X.Y.Z`** (e.g. `release/0.2.3`) for work that **ships a numbered line** — especially when it touches **`pyproject.toml` version**, **`CHANGELOG.md`**, or release-only automation/docs. One release branch per target version keeps PR scope reviewable and avoids mixing the next patch/minor with unrelated work.
- **Before bumping the package version** (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md` release section): **verify the current branch** is the one meant to carry that release (e.g. `git branch --show-current`, confirm you branched from the right base). Do not assume you are on `main` or on the correct `release/*` line; wrong-branch bumps create confusing PRs and tags.
- Small, non-release fixes may still use a **short-lived named branch**; do not pile unrelated commits onto an open **`release/*`** PR without maintainer agreement.
- See **`BRANCH.md`** for the git workflow and **`docs/CI.md`** for what CI runs on PRs.

## Releases: what the maintainer means vs what the agent does

When the maintainer says they want a **new release** or to **ship version X.Y.Z**, they often mean the **product outcome** (users see a version, changelog, optional PyPI), **not** a specific sequence of git commands. Treat it as a **handoff**: do the repo and branch work; tell them clearly what is left for **GitHub / PyPI** in plain language.

### Maintainer (human) — typical steps

No need to memorize git; an agent can prepare the branch. The maintainer usually:

1. **Decides** the target version (e.g. patch vs minor) and what must be in scope.
2. On **GitHub**: open or refresh the **pull request** from `release/X.Y.Z` (or the agreed branch) into `main`, wait for **CI** to pass, then **merge** the PR (squash or merge commit per repo habit).
3. **PyPI** (if applicable): ensure [trusted publishing](https://docs.pypi.org/trusted-publishers/) is configured, then either push git **tag** `vX.Y.Z` or run the **Publish to PyPI** workflow as described in **`docs/VERSIONING.md`**.
4. **Optional:** smoke-test `pip install timelog-extract` after upload.

**Plain terms:** **PR** = request to merge a branch into `main`; **merge** = accept that request on GitHub; **tag** = release label on a commit (often triggers publish); **conflicts** = overlapping edits — resolved **in the branch** by the agent, then pushed, so the PR becomes mergeable again.

### Agent — assume these responsibilities

1. Work on **`release/X.Y.Z`** (or create it from latest **`origin/main`** for a **new** version line). Confirm branch name matches the version being bumped.
2. Apply the **version bump checklist** in **`docs/VERSIONING.md`** (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`, etc.).
3. Run **`./scripts/run_autotests.sh`**; when packaging changes, also **`python -m build`** locally if appropriate.
4. Commit, **`git push origin <branch>`**, and keep the maintainer informed in **non-jargon** terms (“PR is ready”, “CI should run”, “after you merge, tag vX.Y.Z”).
5. **Squash-merge follow-up:** If `main` was updated by **squash-merging** an earlier PR from the **same** `release/X.Y.Z` line, Git history on the branch and on `main` **diverges**. A **second** PR from that branch may show **merge conflicts**. Fix by **`git fetch origin`** and **`git merge origin/main`** into the release branch, resolve conflicts (often **`CHANGELOG.md`**, **`README.md`**), commit the merge, push — see **`docs/VERSIONING.md`** and **`BRANCH.md`**.

## Git worktrees (parallel work)

- Use when: an open PR branch must stay stable, a spike or side idea should not share the same working tree as another agent or task, or you want a second Cursor window on another branch without `stash`/`checkout` churn.
- Prefer sibling worktrees next to the main clone via `./scripts/git_worktree.sh add <branch> [dir-name]` from the primary repo; open the printed path in a separate Cursor window for that branch only.
- Do not mix unrelated commits into an existing PR branch; start a new branch (new worktree or `git switch -c` in an existing tree) for new scope — for **another numbered release**, prefer a fresh **`release/X.Y.Z`** branch from updated `main`.
- Remove finished trees with `./scripts/git_worktree.sh remove …` (or `git worktree remove`); use `git worktree prune` if a directory was deleted manually.

## GitHub Pages (landing site)

- **Production deploy** runs only on **push to `main`** (see **`docs/CI.md`** → *GitHub Pages*). A PR branch is **not** “deployed” until merge; that GitHub label is expected.
- **PRs** run a **verify** job when site files change; merge to `main` to publish. **Re-run deploy:** Actions → *Deploy static content to Pages* → *Run workflow* (`workflow_dispatch`).

## Global Automatic Timelog Setup

- Full setup guide for all local repositories: `GLOBAL_TIMELOG_AUTOMATION.md`.

## Pull requests (language)

- **PR title and PR description must be written in English.** That includes the initial post on GitHub and any edits before merge. Code comments may follow normal project language, but anything reviewers and bots read in the PR thread should be English-only.

## Review Cadence (CodeRabbit)

- Keep PRs in Draft while actively iterating.
- Push work in meaningful batches, not for every micro-change.
- Trigger **`@coderabbitai full review`** when you want a **complete** pass over the whole PR (CodeRabbit ignores its previous inline comments for that run). Use **`@coderabbitai review`** only for an **incremental** pass on new commits since the last full review — if nothing new was pushed, incremental review may do little.
- Trigger that review only when:
  - the current scope is complete enough for review,
  - CI is green (or expected to be green after the latest push),
  - no immediate follow-up commit is expected.
- Resolve review feedback in one consolidated commit when possible.
- Aim for at most 1-2 CodeRabbit review cycles per PR.
- If you use **Draft** PRs, click **Ready for review** once CI and feedback look good. **Open** (non-draft) PRs do not show that button—they are already reviewable; merging without it is fine.
- `@coderabbitai` commands run a review only; they do **not** change Draft or ready state on GitHub.

### CodeRabbit rate limits (GitHub app)

- The **GitHub** integration can hit an **hourly cap on reviewed commits** for your org/plan. If CodeRabbit posts a **“Rate limit exceeded”** message, wait for the countdown (often ~1 hour) or use the **CLI** below instead of `@coderabbitai` on GitHub.
- **Reduce surprises:** batch pushes, then trigger **one** `@coderabbitai full review` when the PR is stable — avoid requesting a full review after every small commit in the same hour.
- **`@coderabbitai help`** in the PR lists commands; product details change over time — treat [CodeRabbit docs](https://docs.coderabbit.ai/) as source of truth for quotas.

### CodeRabbit CLI (optional local pre-check)

- The **CodeRabbit CLI** (`coderabbit`) reviews changes **in your repo** without using GitHub PR review quota. Install and auth: [CodeRabbit CLI docs](https://docs.coderabbit.ai/cli).
- **When:** before pushing a meaningful batch or before `@coderabbitai full review` / `@coderabbitai review` on GitHub, if you want fast feedback on the current branch without waiting on the GitHub app (still subject to [CLI rate limits](https://docs.coderabbit.ai/cli) for your plan).
- **Typical commands** (from repo root): `coderabbit review --base main --type committed` to compare committed changes on your branch to `main`; `coderabbit review --type uncommitted` for unstaged/staged-only changes. Use `--interactive` or `--agent` if you prefer those modes.
- **Note:** CLI and GitHub PR reviews use the same product family but can differ in scope and context; the PR thread remains the merge-facing review for collaborators.

### Release-candidate agent prompt (copy-paste)

- For a **single canonical prompt** (RC tagging, PyPI tag warning, worktrees, `gh pr` deduplication, A/B notes between agents), use **`docs/AGENT_RC_HANDOVER_PROMPT.md`**. Land updates via a normal PR into `main`; until merged, paste from your branch or from GitHub’s file view.

