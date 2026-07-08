# Agent Rules

## Agent fast-path (Cursor/Codex/Claude)

Use this compact execution order before deep exploration:

1. Confirm branch and safety context:
  - `git branch --show-current`
  - `git status --short`
2. For ambiguous or multi-file work, frame the task with
  `docs/decisions/agent-focus-workflow.md` before editing.
3. If release-bound scope, verify branch naming early (`release/X.Y.Z`).
4. Run smallest validating loop first:
  - implement minimal change
  - run targeted test(s)
  - after **CLI-facing** edits, also run `bash scripts/cli_impact_smoke.sh` (see `docs/decisions/agent-inline-cli-ux-validation.md`)
  - then `bash scripts/run_autotests.sh` (repo root; same as CI)
5. For feature flows that are demoed or user-walkthrough critical, run the
  **asciinema expected-outcome loop** before push:
  - define expected observable outcome (what must be visible in terminal output)
  - `asciinema rec` a clean run (prefer isolated `DEMO_HOME`)
  - replay and compare output to expected result
  - fix mismatches and rerun until the expected result is clearly visible
  - reference: `docs/runbooks/asciinema-expected-outcome-loop.md`
6. Prefer non-destructive config handling:
  - never move/delete `timelog_projects.json`
  - use explicit alternate paths (`--projects-config`) for experiments
  - for **URL / gap mapping**, use `gittan review` (interactive) or `gittan review --json` (read-only candidates); `gittan triage-map` is a deprecated alias. Legacy `gittan triage*` and log-cluster `review --uncategorized` are deprecated. Contract: `docs/runbooks/gittan-triage-agents.md`. For triage code reviews: in **Cursor** use `/gittan-triage-review` (or read `.cursor/commands/gittan-triage-review.md` — same checklist in any editor).
7. Keep commits scoped by intent:
  - feature code
  - docs/reorg
  - follow-up cleanup
8. **Before `git push` to `origin`:** run the autotest gate on what you are pushing (same as CI): `bash scripts/run_autotests.sh` from **repository root** — see [`CONTRIBUTING.md`](CONTRIBUTING.md). (`./scripts/run_autotests.sh` is equivalent if the file is executable.) For non-trivial batches, also run **CodeRabbit CLI** when available (`coderabbit review --base main --type committed` — see *CodeRabbit CLI* below). Do not treat “push first, test later” as the default.
9. **When a related PR merges to `main` while your branch stays open:** immediately sync before more edits (`git fetch origin` + `git merge origin/main` or rebase per branch policy), then run the smallest relevant tests. Do not assume "I was notified" means your branch is conflict-safe; overlap in the same files/functions can still require manual resolution.

If this section conflicts with any policy below, the detailed policy below wins.

**Multiple AI tools/editors:** policy stays in this file; for a tool matrix, inspiration vs ideas, and optional skills guidance, see `docs/contributing/ai-assisted-work.md` and `docs/inspiration/README.md`.

**Product doc hierarchy** (vision, scope, metrics, how root `VISION.md` relates): `docs/product/vision-documents.md` — check before substantive product or marketing doc edits.

## Maintainer workflow preferences (low copy-paste)

- The maintainer prefers **as little copy-paste of shell commands as possible** in chat and handoffs. Agents should **run** `git`, `gh`, tests, and similar steps in the environment when possible, and report **outcomes and links** in plain language instead of long runnable command dumps.
- For GitHub follow-ups (PR comments, resolving review threads, listing checks), **use `gh` or the API in the agent session** rather than giving the maintainer a sequence of commands to paste manually.
- When documentation must list commands, keep them **short and canonical** (one script or one doc section); avoid duplicating the same shell in both docs and chat.

## Maintainer TIL (learnings from the human)

*Cross-reference: **TIL** = Today I learned; short glossary in `docs/ideas/team-lexicon.md`.*

- **Prefer, each working day,** to add at least one **TIL** when the maintainer **teaches** something: a correction, a preference, phrasing that works better with agents, product nuance, or “how we do it in this repo.”
- **Where to write it:** `docs/ideas/til/YYYY-MM.md` — one Markdown file per calendar month (create the new month’s file when the first TIL of that month lands). Under a `## YYYY-MM-DD` heading for that day, add a **bulleted** line or two. Keep it **short and durable** — the next human or agent should get the point without the full chat transcript.
- **What to include:** what was learned, and (if it helps) *what to do next time* — not raw chat logs.
- **Same-day is ideal**; if a session runs past midnight, put the TIL on the day the learning happened, or the day you document it, and be consistent in that file.
- **Commit** with normal doc/PR work, or a small `docs: til …` style commit if the learning should land before a larger feature.
- If nothing worth recording happened that day, do **not** pad the file; this is a **useful** log, not a daily quota in an empty form.

## Standard Timelog Policy

- **Worklog path resolution** (matches `[core/config.py](core/config.py)` `resolve_worklog_path` / `default_worklog_path`, `[README.md](README.md)`, and report runs that pass `[core/workspace_root.py](core/workspace_root.py)` `runtime_workspace_root()` as the repo root):
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
- Do not commit a `private/` directory or other gitignored local business notes — including **revenue, detailed metrics, and sponsor-specific numbers** (see `docs/meta/private-local-notes.md`).

## Local data safety (destructive commands)

- **Do not use destructive or irreversible shell steps lightly** when they touch user-owned or gitignored state. Examples: `mv` / `rm` on `timelog_projects.json`, `TIMELOG.md`, dated backups, or anything under `private/`.
- Before renaming, moving aside, or deleting files that are the **only copy** of configuration or work history, **confirm with the user** or use a **non-destructive** pattern first (e.g. `cp` to a timestamped path outside the repo, or document exact restore steps).
- Scenario testing and “quick cleanup” are common ways to lose data; treat `timelog_projects.json` as **critical** even though it is gitignored.
- **Closed / invoiced months:** `~/.gittan/invoice/invoiced/ledger.yaml` is **authoritative** for what was billed — never trust a fresh `gittan report` of an old month (collector evidence decays as sources rotate). The observed cache (`~/.gittan/observed/`) is a keep-max high-water mark that a report run can only raise, never lower — but it is a convenience, not invoiced truth; reconcile closed months against the ledger and `reported/`.
- **Incident references:** project config lost during manual matrix scenario work (`docs/incidents/2026-04-13-project-config-backup-gap.md`); observed cache silently degraded by reports on closed months (`docs/incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md`).

## Branch policy (`main` + short-lived `task/*`)

- **`main` is branch-protected** (no direct push). Keep it release-ready and merge only via PR.
- Agents should create **short-lived task branches from `main`** (for example `task/<scope>`), open PR `task/* -> main`, merge, then delete the task branch.
- Avoid long-lived branch families (`feat/*`, `fix/*`, `docs/*`, `cursor/*`) unless explicitly requested for a special case.
- Release flow:
  1. Merge ordinary work to `main` via PR when ready.
  2. Use `release/X.Y.Z` when versioning/release chores need explicit isolation; PR `release/* -> main` when that line is ready.
- Review intent: `task/* -> main` carries feature/docs review; keep PRs small enough to review in one pass.
- **Before bumping versioned files** (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`): confirm branch intent with `git branch --show-current`.
- If a **separate `dev`** branch exists (fork or policy), divergence handling lives in `docs/runbooks/dev-main-alignment.md` — default upstream is `main` only.
- See `BRANCH.md` for the operational workflow and `docs/runbooks/ci.md` for CI behavior.

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
3. **PyPI** (if applicable): ensure [trusted publishing](https://docs.pypi.org/trusted-publishers/) is configured, then either push git **tag** `vX.Y.Z` or run the **Publish to PyPI** workflow as described in `docs/runbooks/versioning.md`.
4. **Optional:** smoke-test `pip install timelog-extract` after upload.

**Plain terms:** **PR** = request to merge a branch into `main`; **merge** = accept that request on GitHub; **tag** = release label on a commit (often triggers publish); **conflicts** = overlapping edits — resolved **in the branch** by the agent, then pushed, so the PR becomes mergeable again.

### Agent — assume these responsibilities

1. Work on `release/X.Y.Z` (or create it from latest `origin/main` for a **new** version line). Confirm branch name matches the version being bumped.
2. Apply the **version bump checklist** in `docs/runbooks/versioning.md` (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`, etc.).
3. Run `bash scripts/run_autotests.sh` (repo root); when packaging changes, also `python -m build` locally if appropriate.
4. Commit, `git push origin <branch>`, and keep the maintainer informed in **non-jargon** terms (“PR is ready”, “CI should run”, “after you merge, tag vX.Y.Z”).
5. **Squash-merge follow-up:** If `main` was updated by **squash-merging** an earlier PR from the **same** `release/X.Y.Z` line, Git history on the branch and on `main` **diverges**. A **second** PR from that branch may show **merge conflicts**. Fix by `git fetch origin` and `git merge origin/main` into the release branch, resolve conflicts (often `CHANGELOG.md`, `README.md`), commit the merge, push — see `docs/runbooks/versioning.md` and `BRANCH.md`.

## Git worktrees (parallel work)

- Use when: an open PR branch must stay stable, a spike or side idea should not share the same working tree as another agent or task, or you want a second Cursor window on another branch without `stash`/`checkout` churn.
- Prefer sibling worktrees next to the main clone via `./scripts/git_worktree.sh add <branch> [dir-name]` from the primary repo; open the printed path in a separate Cursor window for that branch only.
- Do not mix unrelated commits into an existing PR branch; start a new branch (new worktree or `git switch -c` in an existing tree) for new scope — for **another numbered release**, prefer a fresh `release/X.Y.Z` branch from updated `main`.
- Remove finished trees with `./scripts/git_worktree.sh remove …` (or `git worktree remove`); use `git worktree prune` if a directory was deleted manually.

## GitHub Pages (landing site)

- **Production deploy** runs only on **push to `main`** (see `docs/runbooks/ci.md` -> *GitHub Pages*). A PR branch is **not** "deployed" until merge; that GitHub label is expected.
- **PRs** run a **verify** job when site files change; merge to `main` to publish. **Re-run deploy:** Actions → *Deploy static content to Pages* → *Run workflow* (`workflow_dispatch`).

## Global Automatic Timelog Setup

- Global timelog (machine-wide hooks): `docs/runbooks/global-timelog-setup.md` (historical detail: `docs/legacy/global-timelog-automation-legacy.md`).

## Pull requests (language)

- **PR title and PR description must be written in English.** That includes the initial post on GitHub and any edits before merge. Code comments may follow normal project language, but anything reviewers and bots read in the PR thread should be English-only.
- **This applies to every GitHub artifact, not just PRs** — issue bodies and comments, and **manual-test / handoff checklists** posted by `scripts/rabbit_handoff.sh` or by hand, are English-only. Chat replies to the maintainer may use his language; anything published to GitHub is English.

## Pull requests (issue linking — keep the board in sync)

Story status on the GitHub board drifts because PRs reference issues in the
**title** (`GH-284`, `#238`) but rarely give GitHub a closing keyword to act on.
Fix it at the source — every PR body must link its issue with a keyword GitHub
parses:

- **Fully delivers the issue** → `Closes #<github-issue-number>` (auto-closes on
  merge). Use the **GitHub issue number** (`#263`), not the story id (`GH-186`).
- **One slice/phase of a larger issue** → `Part of #<number>` (keeps it open; the
  issue stays as the running tracker). Never `Closes` a multi-slice issue from a
  single slice.
- **Story id vs issue number:** `GH-NNN` is the *story id* (lives in the spec under
  `docs/task-prompts/`); `#NNN` is the *GitHub issue/PR number*. They do **not**
  match 1:1 (e.g. story `GH-186` is issue `#263`). Put the story id in the title
  for humans **and** the `Closes/Part of #NNN` line in the body for GitHub.
- **Slices leave a trail:** when a PR ships slice N of M, its body states what
  remains (`Deferred to slice N+1: …`) so the still-open issue reflects reality.
- **When no keyword fits** (pure docs/tooling with no issue), that's fine — but if
  an issue exists, link it.

## Documentation paths in code (CLI, errors, `console.print`)

- **Do not** point user-facing code (Python CLI output, error helpers, extension copy) at `docs/legacy/`. Those files are not maintained as operational truth.
- **Do** reference maintained docs: typically `docs/runbooks/` for procedures, `docs/decisions/` for policy, `docs/specs/` for behavior contracts, `docs/product/` for product truth. If the right doc does not exist yet, add a short runbook and link optional history from there.
- Markdown (README, `docs/README.md`, changelogs) may still mention `docs/legacy/` as secondary context.

## Documentation privacy and path hygiene

- In docs/specs/prompts, use **repo-relative paths** (for example
`docs/task-prompts/example.md`) instead of absolute local paths.
- Never include local home paths or user-identifying filesystem segments (for
example `/Users/<name>/...`) in committed documentation **or in any GitHub
artifact** — issue/PR bodies and comments, and manual-test / handoff checklists.
Tell the maintainer to run tools from the **repo root** with `gittan-dev` (or the
installed `gittan`); never a private worktree path such as `.claude/worktrees/...`.
Use `~/.gittan` (tilde), not the expanded home. This is why `scripts/rabbit_handoff.sh`
should refuse to post a checklist body containing `/Users/`, `/home/`, or
`.claude/worktrees/`.
- Keep attribution neutral in specs (for example `Owner: Maintainer`) and avoid
personal identifiers unless explicitly required for a formal incident record.
- **Never publish the maintainer's real business data in any GitHub artifact.**
That includes **real hours/amounts per project or client**, **client/project
names tied to those numbers**, invoice/ledger figures, and **live config values**
(profile `match_terms`, `tracked_urls`, customer repos/usernames from
`timelog_projects.json`). Real-data validation (e.g. a before/after report diff to
check an attribution change) is valuable, but its **numbers and names stay in chat
with the maintainer only** — on GitHub, describe it in the abstract ("shifts small
amounts across a few profiles"), with no figures, client names, or config values.
When in doubt, anonymize or omit.

## Test and fixture data hygiene (mandatory)

- Never hardcode maintainer/customer/project-specific names from a live local
environment into tests, fixtures, prompts, or docs examples.
- Use neutral placeholders in new tests and examples (for example
`project-alpha`, `project-beta`, `customer-a.test`, `customer-b.test`).
- Before commit/push, scan changed files for accidental real-world identifiers
(personal usernames, customer domains, repo names) and replace with generic
fixtures unless the value is part of a deliberate public canonical example.
- For wizard/edit UX changes, add or update a test that proves **safe editing**
behavior: editing one step must not silently overwrite unrelated selections.
- If a real identifier was accidentally introduced, treat it as a blocker:
remove it, rerun tests, and document the correction in the PR notes.

## Review Cadence (CodeRabbit)

- **Severity and who may fix what:** see `docs/decisions/agent-review-contract.md` (draft contract between review signal and human/Cursor execution).
- Keep PRs in Draft while actively iterating.
- Push work in meaningful batches, not for every micro-change.
- Keep CodeRabbit auto-review enabled; throttle manual review commands to at most
one trigger per stable batch.
- Trigger `@coderabbitai full review` when you want a **complete** pass over the whole PR (CodeRabbit ignores its previous inline comments for that run). Use `@coderabbitai review` only for an **incremental** pass on new commits since the last full review — if nothing new was pushed, incremental review may do little.
- Trigger that review only when:
  - the current scope is complete enough for review,
  - CI is green (or expected to be green after the latest push),
  - no immediate follow-up commit is expected.
- Resolve review feedback in one consolidated commit when possible.
- **Review close-out routine (3 steps — do these once per review cycle, not per comment):**
  1. **Read all comments first.** Categorise each as: fix, explain (not an issue / pre-existing), or escalate (needs maintainer decision). Do not start committing until you have read every thread.
  2. **Fix valid findings in one consolidated commit** (or two if the scope is clearly different). Run `bash scripts/run_autotests.sh` before pushing.
  3. **Reply to every open thread** — even ones you are not fixing — with one of:
    - Fixed: `Addressed in <sha>: <what changed>`
    - Explained: `Not applicable — <reason>` (e.g. pre-existing on main, misread, accepted trade-off)
    - Escalated: `Needs maintainer decision — <why>`
- Do not silently resolve threads: always leave a short commit-linked note first.
- Keep a thread open only when verification or product decision is still pending.
- Aim for at most 1-2 CodeRabbit review cycles per PR.
- If you use **Draft** PRs, click **Ready for review** once CI and feedback look good. **Open** (non-draft) PRs do not show that button—they are already reviewable; merging without it is fine.
- `@coderabbitai` commands run a review only; they do **not** change Draft or ready state on GitHub.

### CodeRabbit rate limits (GitHub app)

- The **GitHub** integration can hit an **hourly cap on reviewed commits** for your org/plan. If CodeRabbit posts a **“Rate limit exceeded”** message, wait for the countdown (often ~1 hour) or use the **CLI** below instead of `@coderabbitai` on GitHub.
- **Reduce surprises:** batch pushes, then trigger **one** `@coderabbitai full review` when the PR is stable — avoid requesting a full review after every small commit in the same hour.
- `@coderabbitai help` in the PR lists commands; product details change over time — treat [CodeRabbit docs](https://docs.coderabbit.ai/) as source of truth for quotas.

### CodeRabbit CLI (optional local pre-check)

- The **CodeRabbit CLI** (`coderabbit`) reviews changes **in your repo** without using GitHub PR review quota. Install and auth: [CodeRabbit CLI docs](https://docs.coderabbit.ai/cli).
- **When:** before pushing a meaningful batch or before `@coderabbitai full review` / `@coderabbitai review` on GitHub, if you want fast feedback on the current branch without waiting on the GitHub app (still subject to [CLI rate limits](https://docs.coderabbit.ai/cli) for your plan).
- **Typical commands** (from repo root): `coderabbit review --base main --type committed` to compare committed changes on your branch to `main`; `coderabbit review --type uncommitted` for unstaged/staged-only changes. Use `--interactive` or `--agent` if you prefer those modes.
- **Note:** CLI and GitHub PR reviews use the same product family but can differ in scope and context; the PR thread remains the merge-facing review for collaborators.

### Kanin-loop (CodeRabbit convergence loop — any agent)

- **What:** an editor-agnostic loop-engineering pass — implement → `scripts/rabbit_loop.sh` (CodeRabbit `--agent` + `scripts/run_autotests.sh`) → fix **within** `docs/decisions/agent-review-contract.md` → repeat until `RABBIT_LOOP: CONVERGED` (iteration cap 3). Canonical workflow: **`docs/skills/rabbit-loop.md`**.
- **Ship gate (by judgment, not file type):** after converging, push + open the PR, then `scripts/rabbit_loop.sh --classify-merge`. `MERGE_CLASS: SAFE` (auto-merge when CONVERGED) for everything **except** human-judgment surfaces — the report/invoice number engine (`core/domain.py`, `core/analytics.py`, `core/project_hours.py`, `core/pipeline.py`, `core/truth_payload.py`, `core/report_*`), `collectors/`, `outputs/`, `pyproject.toml`, `.github/`, `AGENTS.md`/`CLAUDE.md`. Those are `NEEDS_HUMAN` → generate a concrete checklist with `scripts/rabbit_loop.sh --manual-test-plan` (real command + judgeable expected outcome per step), post it, and pause for the maintainer. Never auto-merge unless `CONVERGED`.
- **Board handoff (`NEEDS_HUMAN` → "Needs manual testing"):** park the pause on [Project 3](https://github.com/users/mbjorke/projects/3) with `scripts/rabbit_handoff.sh --issue N` — it sets the issue's board Status to **`Needs manual testing`** and posts the checklist as a comment (`--dry-run` to preview; refuses `SAFE` without `--force`; needs `gh auth refresh -s project`). Status flow: `In review → SAFE+CONVERGED → Done (auto)` or `In review → NEEDS_HUMAN+CONVERGED → Needs manual testing → Done`. It is the only kanin-loop script that writes to GitHub; `rabbit_loop.sh` stays read-only. Canonical: `docs/skills/rabbit-loop.md`.
- **Per agent:** Claude Code and Cursor expose `/rabbit-loop`; **Zed, Codex, Conductor, Antigravity** (and any shell-capable agent) run `scripts/rabbit_loop.sh` directly and follow the canonical doc. Base defaults to `origin/main` — keep it fresh (a stale local `main` inflates the review).

### Task handover prompt (copy-paste)

- For a **single canonical prompt** (release tagging, PyPI tag warning, worktrees, `gh pr` deduplication, A/B notes between agents), use `docs/contributing/agent-task-handover-prompt.md`. Land updates via a normal PR into `main`; until merged, paste from your branch or from GitHub’s file view.

## Task spec traceability (required)

- Every new or updated task spec/prompt in `docs/task-prompts/` must include a
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

