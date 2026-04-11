# Agent Rules

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

## Git worktrees (parallel work)

- Use when: an open PR branch must stay stable, a spike or side idea should not share the same working tree as another agent or task, or you want a second Cursor window on another branch without `stash`/`checkout` churn.
- Prefer sibling worktrees next to the main clone via `./scripts/git_worktree.sh add <branch> [dir-name]` from the primary repo; open the printed path in a separate Cursor window for that branch only.
- Do not mix unrelated commits into an existing PR branch; start a new branch (new worktree or `git switch -c` in an existing tree) for new scope.
- Remove finished trees with `./scripts/git_worktree.sh remove …` (or `git worktree remove`); use `git worktree prune` if a directory was deleted manually.

## Global Automatic Timelog Setup

- Full setup guide for all local repositories: `GLOBAL_TIMELOG_AUTOMATION.md`.

## Pull requests (language)

- **PR title and PR description must be written in English.** That includes the initial post on GitHub and any edits before merge. Code comments may follow normal project language, but anything reviewers and bots read in the PR thread should be English-only.

## Review Cadence (CodeRabbit)

- Keep PRs in Draft while actively iterating.
- Push work in meaningful batches, not for every micro-change.
- Trigger `@coderabbitai review` only when:
  - the current scope is complete enough for review,
  - CI is green (or expected to be green after the latest push),
  - no immediate follow-up commit is expected.
- Resolve review feedback in one consolidated commit when possible.
- Aim for at most 1-2 CodeRabbit review cycles per PR.
- Mark PR "Ready for review" after CI + review feedback are addressed.

