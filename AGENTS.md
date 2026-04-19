# Agent Rules

## Agent fast-path (Cursor/Codex/Claude)

Use this compact execution order before deep exploration:

1. Confirm branch and safety context:
   - `git branch --show-current`
   - `git status --short`
2. If release-bound scope, verify branch naming early (`release/X.Y.Z`).
3. Run smallest validating loop first:
   - implement minimal change
   - run targeted test(s)
   - after **CLI-facing** edits, also run `bash scripts/cli_impact_smoke.sh` (see `docs/decisions/agent-inline-cli-ux-validation.md`)
   - then `bash scripts/run_autotests.sh` (repo root; same as CI)
4. Prefer non-destructive config handling:
   - never move/delete `timelog_projects.json`
   - use explicit alternate paths (`--projects-config`) for experiments
5. Keep commits scoped by intent:
   - feature code
   - docs/reorg
   - follow-up cleanup
6. **Before `git push` to `origin`:** run the autotest gate on what you are pushing (same as CI): **`bash scripts/run_autotests.sh`** from **repository root** — see [`CONTRIBUTING.md`](CONTRIBUTING.md). (`./scripts/run_autotests.sh` is equivalent if the file is executable.) For non-trivial batches, also run **CodeRabbit CLI** when available (`coderabbit review --base main --type committed` — see *CodeRabbit CLI* below). Do not treat “push first, test later” as the default.

If this section conflicts with any policy below, the detailed policy below wins.

**Multiple AI tools/editors:** policy stays in this file; for a tool matrix, inspiration vs ideas, and optional skills guidance, see **`docs/contributing/ai-assisted-work.md`** and **`docs/inspiration/README.md`**.

**Product doc hierarchy** (vision, scope, metrics, how root `VISION.md` relates): **`docs/product/vision-documents.md`** — check before substantive product or marketing doc edits.

## Maintainer workflow preferences (low copy-paste)

- The maintainer prefers **as little copy-paste of shell commands as possible** in chat and handoffs. Agents should **run** `git`, `gh`, tests, and similar steps in the environment when possible, and report **outcomes and links** in plain language instead of long runnable command dumps.
- For GitHub follow-ups (PR comments, resolving review threads, listing checks), **use `gh` or the API in the agent session** rather than giving the maintainer a sequence of commands to paste manually.
- When documentation must list commands, keep them **short and canonical** (one script or one doc section); avoid duplicating the same shell in both docs and chat.

## Maintainer TIL (learnings from the human)

*Cross-reference: **TIL** = *Today I learned*; short glossary in `docs/ideas/team-lexicon.md`.*

- **Prefer, each working day,** to add at least one **TIL** when the maintainer **teaches** something: a correction, a preference, phrasing that works better with agents, product nuance, or “how we do it in this repo.”
- **Where to write it:** `docs/ideas/til/YYYY-MM.md` — one Markdown file per calendar month (create the new month’s file when the first TIL of that month lands). Under a `## YYYY-MM-DD` heading for that day, add a **bulleted** line or two. Keep it **short and durable** — the next human or agent should get the point without the full chat transcript.
- **What to include:** what was learned, and (if it helps) *what to do next time* — not raw chat logs.
- **Same-day is ideal**; if a session runs past midnight, put the TIL on the day the learning happened, or the day you document it, and be consistent in that file.
- **Commit** with normal doc/PR work, or a small `docs: til …` style commit if the learning should land before a larger feature.
- If nothing worth recording happened that day, do **not** pad the file; this is a **useful** log, not a daily quota in an empty form.

## Standard Timelog Policy

- **Worklog path resolution** (matches [`core/config.py`](core/config.py) `resolve_worklog_path` / `default_worklog_path`, [`README.md`](README.md), and report runs that pass [`core/workspace_root.py`](core/workspace_root.py) `runtime_workspace_root()` as the repo root):
  1. If `--worklog PATH` is provided, use that path — **overrides the default** resolution for that run.
  2. Else if `timelog_projects.json` sets a top-level `worklog` string, resolve it (relative paths are relative to the config file’s directory).
  3. Else if `TIMELOG.md` exists in the **current working directory**, use that file.
  4. Else use `<current_repo_root>/TIMELOG.md`, where `<current_repo_root>` is the Git repository root from `git rev-parse --show-toplevel` when that succeeds, otherwise the current working directory. If the file does not exist yet, create it at this path before logging work.
- **By default** (no `--worklog` and no config `worklog`), resolution uses steps 3–4 above.
- Add entries during/after meaningful work using this format:
  - `## YYYY-MM-DD HH:MM`
  - `- <short summary of what was done>`
- **Clock time must be real local wall time** when the entry is written. Do not invent, round to a “nice” hour, or default to placeholder times (for example `18:00`). Wrong timestamps defeat the purpose of the log.
- **How to get the time:** run `date '+%Y-%m-%d %H:%M'` in the repo environment and use that for `YYYY-MM-DD HH:MM`, or use a time the user explicitly stated in the thread. If neither is available, ask the user before appending an entry.
- **Resolution order (for agents):** use the numbered list above (same four steps).

## Git Safety

- Never commit `TIMELOG.md`.
- Ensure `TIMELOG.md` remains gitignored.
- If `TIMELOG.md` is accidentally staged, unstage it before commit.
- Do not commit a `**private/`** directory or other gitignored local business notes — including **revenue, detailed metrics, and sponsor-specific numbers** (see `**docs/meta/private-local-notes.md`**).

## Local data safety (destructive commands)

- **Do not use destructive or irreversible shell steps lightly** when they touch user-owned or gitignored state. Examples: `mv` / `rm` on **`timelog_projects.json`**, **`TIMELOG.md`**, dated backups, or anything under **`private/`**.
- Before renaming, moving aside, or deleting files that are the **only copy** of configuration or work history, **confirm with the user** or use a **non-destructive** pattern first (e.g. `cp` to a timestamped path outside the repo, or document exact restore steps).
- Scenario testing and “quick cleanup” are common ways to lose data; treat `**timelog_projects.json`** as **critical** even though it is gitignored.
- **Incident reference** (project config lost during manual matrix scenario work, recovery from git history): **`docs/incidents/2026-04-13-project-config-backup-gap.md`**.

## Branch policy (`main` + short-lived `task/*`)

- **`main` is branch-protected** (no direct push). Keep it release-ready and merge only via PR.
- Agents should create **short-lived task branches from `main`** (for example `task/<scope>`), open PR **`task/* -> main`**, merge, then delete the task branch.
- Avoid long-lived branch families (`feat/*`, `fix/*`, `docs/*`, `cursor/*`) unless explicitly requested for a special case.
- Release flow:
  1. Merge ordinary work to **`main`** via PR when ready.
  2. Use **`release/X.Y.Z`** when versioning/release chores need explicit isolation; PR **`release/* -> main`** when that line is ready.
- Review intent: **`task/* -> main`** carries feature/docs review; keep PRs small enough to review in one pass.
- **Before bumping versioned files** (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`): confirm branch intent with `git branch --show-current`.
- If a **separate `dev`** branch exists (fork or policy), divergence handling lives in **`docs/runbooks/dev-main-alignment.md`** — default upstream is **`main` only**.
- See **`BRANCH.md`** for the operational workflow and **`docs/runbooks/ci.md`** for CI behavior.

## Naming migration (`rc-` -> `task-`)

- `rc-` naming is now considered **legacy** for day-to-day feature work.
- Use `task/*` branch names for agent-delivered feature scope.
- For prompt/story docs, prefer `docs/task-prompts/` for new material.
- Use `docs/task-prompts/` for prompt/story docs; avoid creating new `rc-` names for feature work.

## Releases: what the maintainer means vs what the agent does

When the maintainer says they want a **new release** or to **ship version X.Y.Z**, they often mean the **product outcome** (users see a version, changelog, optional PyPI), **not** a specific sequence of git commands. Treat it as a **handoff**: do the repo and branch work; tell them clearly what is left for **GitHub / PyPI** in plain language.

### Maintainer (human) — typical steps

No need to memorize git; an agent can prepare the branch. The maintainer usually:

1. **Decides** the target version (e.g. patch vs minor) and what must be in scope.
2. On **GitHub**: open or refresh the **pull request** from `release/X.Y.Z` (or the agreed branch) into `main`, wait for **CI** to pass, then **merge** the PR (squash or merge commit per repo habit).
3. **PyPI** (if applicable): ensure [trusted publishing](https://docs.pypi.org/trusted-publishers/) is configured, then either push git **tag** `vX.Y.Z` or run the **Publish to PyPI** workflow as described in **`docs/runbooks/versioning.md`**.
4. **Optional:** smoke-test `pip install timelog-extract` after upload.

**Plain terms:** **PR** = request to merge a branch into `main`; **merge** = accept that request on GitHub; **tag** = release label on a commit (often triggers publish); **conflicts** = overlapping edits — resolved **in the branch** by the agent, then pushed, so the PR becomes mergeable again.

### Agent — assume these responsibilities

1. Work on `**release/X.Y.Z`** (or create it from latest `**origin/main`** for a **new** version line). Confirm branch name matches the version being bumped.
2. Apply the **version bump checklist** in `**docs/runbooks/versioning.md`** (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`, etc.).
3. Run `**bash scripts/run_autotests.sh**` (repo root); when packaging changes, also `**python -m build`** locally if appropriate.
4. Commit, `**git push origin <branch>**`, and keep the maintainer informed in **non-jargon** terms (“PR is ready”, “CI should run”, “after you merge, tag vX.Y.Z”).
5. **Squash-merge follow-up:** If `main` was updated by **squash-merging** an earlier PR from the **same** `release/X.Y.Z` line, Git history on the branch and on `main` **diverges**. A **second** PR from that branch may show **merge conflicts**. Fix by `**git fetch origin`** and `**git merge origin/main`** into the release branch, resolve conflicts (often `**CHANGELOG.md`**, `**README.md**`), commit the merge, push — see `**docs/runbooks/versioning.md**` and `**BRANCH.md**`.

## Git worktrees (parallel work)

- Use when: an open PR branch must stay stable, a spike or side idea should not share the same working tree as another agent or task, or you want a second Cursor window on another branch without `stash`/`checkout` churn.
- Prefer sibling worktrees next to the main clone via `./scripts/git_worktree.sh add <branch> [dir-name]` from the primary repo; open the printed path in a separate Cursor window for that branch only.
- Do not mix unrelated commits into an existing PR branch; start a new branch (new worktree or `git switch -c` in an existing tree) for new scope — for **another numbered release**, prefer a fresh **`release/X.Y.Z`** branch from updated `main`.
- Remove finished trees with `./scripts/git_worktree.sh remove …` (or `git worktree remove`); use `git worktree prune` if a directory was deleted manually.

## GitHub Pages (landing site)

- **Production deploy** runs only on **push to `main`** (see `**docs/runbooks/ci.md**` → *GitHub Pages*). A PR branch is **not** “deployed” until merge; that GitHub label is expected.
- **PRs** run a **verify** job when site files change; merge to `main` to publish. **Re-run deploy:** Actions → *Deploy static content to Pages* → *Run workflow* (`workflow_dispatch`).

## Global Automatic Timelog Setup

- Global timelog (machine-wide hooks): `docs/runbooks/global-timelog-setup.md` (historical detail: `docs/legacy/global-timelog-automation-legacy.md`).

## Pull requests (language)

- **PR title and PR description must be written in English.** That includes the initial post on GitHub and any edits before merge. Code comments may follow normal project language, but anything reviewers and bots read in the PR thread should be English-only.

## Documentation paths in code (CLI, errors, `console.print`)

- **Do not** point user-facing code (Python CLI output, error helpers, extension copy) at **`docs/legacy/`**. Those files are not maintained as operational truth.
- **Do** reference maintained docs: typically **`docs/runbooks/`** for procedures, **`docs/decisions/`** for policy, **`docs/specs/`** for behavior contracts, **`docs/product/`** for product truth. If the right doc does not exist yet, add a short runbook and link optional history from there.
- Markdown (README, `docs/README.md`, changelogs) may still mention `docs/legacy/` as secondary context.

## Documentation privacy and path hygiene

- In docs/specs/prompts, use **repo-relative paths** (for example
  `docs/task-prompts/example.md`) instead of absolute local paths.
- Never include local home paths or user-identifying filesystem segments (for
  example `/Users/<name>/...`) in committed documentation.
- Keep attribution neutral in specs (for example `Owner: Maintainer`) and avoid
  personal identifiers unless explicitly required for a formal incident record.

## Review Cadence (CodeRabbit)

- **Severity and who may fix what:** see **`docs/decisions/agent-review-contract.md`** (draft contract between review signal and human/Cursor execution).

- Keep PRs in Draft while actively iterating.
- Push work in meaningful batches, not for every micro-change.
- Keep CodeRabbit auto-review enabled; throttle manual review commands to at most
  one trigger per stable batch.
- Trigger **`@coderabbitai full review`** when you want a **complete** pass over the whole PR (CodeRabbit ignores its previous inline comments for that run). Use **`@coderabbitai review`** only for an **incremental** pass on new commits since the last full review — if nothing new was pushed, incremental review may do little.
- Trigger that review only when:
  - the current scope is complete enough for review,
  - CI is green (or expected to be green after the latest push),
  - no immediate follow-up commit is expected.
- Resolve review feedback in one consolidated commit when possible.
- When feedback is fixed, reply in the same thread with a short note like
  `Addressed in <sha>: <what changed>`, then resolve the thread.
- Do not silently resolve threads: always leave a short commit-linked note first.
- Keep a thread open only when verification or product decision is still pending.
- Aim for at most 1-2 CodeRabbit review cycles per PR.
- If you use **Draft** PRs, click **Ready for review** once CI and feedback look good. **Open** (non-draft) PRs do not show that button—they are already reviewable; merging without it is fine.
- `@coderabbitai` commands run a review only; they do **not** change Draft or ready state on GitHub.

### CodeRabbit rate limits (GitHub app)

- The **GitHub** integration can hit an **hourly cap on reviewed commits** for your org/plan. If CodeRabbit posts a **“Rate limit exceeded”** message, wait for the countdown (often ~1 hour) or use the **CLI** below instead of `@coderabbitai` on GitHub.
- **Reduce surprises:** batch pushes, then trigger **one** `@coderabbitai full review` when the PR is stable — avoid requesting a full review after every small commit in the same hour.
- `**@coderabbitai help`** in the PR lists commands; product details change over time — treat [CodeRabbit docs](https://docs.coderabbit.ai/) as source of truth for quotas.

### CodeRabbit CLI (optional local pre-check)

- The **CodeRabbit CLI** (`coderabbit`) reviews changes **in your repo** without using GitHub PR review quota. Install and auth: [CodeRabbit CLI docs](https://docs.coderabbit.ai/cli).
- **When:** before pushing a meaningful batch or before `@coderabbitai full review` / `@coderabbitai review` on GitHub, if you want fast feedback on the current branch without waiting on the GitHub app (still subject to [CLI rate limits](https://docs.coderabbit.ai/cli) for your plan).
- **Typical commands** (from repo root): `coderabbit review --base main --type committed` to compare committed changes on your branch to `main`; `coderabbit review --type uncommitted` for unstaged/staged-only changes. Use `--interactive` or `--agent` if you prefer those modes.
- **Note:** CLI and GitHub PR reviews use the same product family but can differ in scope and context; the PR thread remains the merge-facing review for collaborators.

### Task handover prompt (copy-paste)

- For a **single canonical prompt** (release tagging, PyPI tag warning, worktrees, `gh pr` deduplication, A/B notes between agents), use `**docs/contributing/agent-task-handover-prompt.md`**. Land updates via a normal PR into `main`; until merged, paste from your branch or from GitHub’s file view.

## Task spec traceability (required)

- Every new or updated task spec/prompt in `**docs/task-prompts/**` must include a
  canonical `## Traceability` section using the exact field keys below.
- Story ID must use your canonical tracker prefix, for example `GH-123` (GitHub)
  or `JIRA-123` (Jira). Do not use free-form IDs.
- Required fields and allowed values:
  - `story_id`: string (`GH-123`, `JIRA-123`, etc.)
  - `spec_status`: `draft | approved | superseded`
  - `implementation_status`: `not built | in progress | built | verified`
  - `created_at`: date `YYYY-MM-DD`
  - `last_updated_at`: date `YYYY-MM-DD`
  - `implementation.pr`: string (URL or PR reference)
  - `implementation.branch`: string
  - `implementation.commits`: list of commit SHAs
  - `validation.evidence`: string (path/URL/note)
  - `validation.decision`: `GO | conditional GO | NO-GO`
  - `changelog`: list of dated notes
- Canonical format example (copy shape exactly):

  ```md
  ## Traceability

  - story_id: GH-123
  - spec_status: draft
  - implementation_status: not built
  - created_at: 2026-04-15
  - last_updated_at: 2026-04-15
  - implementation.pr: pending
  - implementation.branch: pending
  - implementation.commits: []
  - validation.evidence: pending
  - validation.decision: NO-GO
  - changelog:
    - 2026-04-15: Initial draft created.
  ```

- Any change to requirements, thresholds, gates, or acceptance criteria must
  update `last_updated_at` and append a short note to `changelog`.
- If a spec has no implementation yet, `implementation_status` must explicitly
  be `not built` (never implicit).