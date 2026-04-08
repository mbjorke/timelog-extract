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

