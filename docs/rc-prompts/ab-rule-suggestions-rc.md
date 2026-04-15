# RC Prompt: A/B Suggestions For Uncategorized Rules

Use this prompt when preparing a release candidate implementation of A/B rule suggestions.

## Scope

Implement a v1 assistant flow that proposes rule updates for uncategorized events,
split into Option A (`safe`) and Option B (`broad`), with explicit user confirmation
before writing `timelog_projects.json`.

## Required behavior

- Add CLI entrypoint(s) for suggestion generation and apply.
- Build suggestions from uncategorized event clusters in selected timeframe.
- Display impact preview:
  - estimated `+events`
  - estimated `+hours`
  - estimated `-uncategorized`
- Require explicit confirmation before applying.
- Create a backup before writing config.

## Constraints

- Keep existing `gittan review` workflow functional.
- Do not introduce destructive behavior.
- Preserve local-first behavior.
- Keep output concise and readable in terminal.

## Test plan

- Unit tests for:
  - clustering-to-suggestion mapping
  - A vs B partition logic
  - impact preview calculations
  - backup + apply behavior
- Manual smoke:
  - run on a real day with uncategorized events
  - verify A/B output quality
  - verify rollback path using backup

## Deliverables checklist

- CLI command docs/help updated
- Implementation with explicit confirm gate
- Backup-before-write path implemented
- Tests added and passing
- Changelog `Unreleased` updated

