# Agent Rules

## Standard Timelog Policy

- Use exactly one local timelog file: `TIMELOG.md` in repo root.
- If `TIMELOG.md` does not exist, create it before logging work.
- Add entries during/after meaningful work using this format:
  - `## YYYY-MM-DD HH:MM`
  - `- <short summary of what was done>`

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

