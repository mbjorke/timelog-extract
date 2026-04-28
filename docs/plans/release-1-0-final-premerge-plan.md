# Release 1.0 Final Pre-Merge Plan

Status: planning checkpoint before merge/release of current batch
Last updated: 2026-04-28

## Highest priority now

- Close remaining items in `docs/runbooks/cli-first-v1-release-checklist.md`.
- Close Slice 1 planning/contract lock path in `docs/tasks/timelog-truth-slice1-close-plan.md` (implementation can follow in next focused batch).
- Keep all non-critical feature ideas open until after 1.0 tag.

## Scope decisions for current release window

- In scope:
  - CLI-first release gates.
  - Slice 1 planning clarity and contract freeze preparation.
  - Jira-sync polish items already listed as P0 in `docs/runbooks/cli-polish-backlog-release-1-0.md`.
- Out of scope for this merge/release batch:
  - New integrations (calendar/CALDAV, broader sync expansions, etc.).
  - DB cache v1 and other post-1.0 features.

## Worklog-first strategy status (for release clarity)

- Current runtime behavior is present and usable:
  - `source_strategy` supports `auto|worklog-first|balanced`.
  - `auto` resolves to `worklog-first` when readable worklog exists; otherwise falls back to `balanced`.
  - Payload already includes `source_strategy_requested`, `source_strategy_effective`, and `primary_source`.
- Release interpretation:
  - Treat as partial/usable behavior in v1.
  - Do not expand strategy scope in this final pre-merge window unless it blocks CLI-first release gates.

## Final pre-merge validation intent

- Run one final CodeRabbit CLI pass on committed changes.
- Address only high-signal findings that affect release safety/clarity.
- Avoid broad new changes after the final review loop.
