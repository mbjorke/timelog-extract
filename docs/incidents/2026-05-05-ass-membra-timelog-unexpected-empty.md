# Incident: ass-membra TIMELOG unexpectedly empty

## Date

- 2026-05-05

## Summary

- `ass-membra/TIMELOG.md` was observed as `0` bytes even though prior workflow expected historical content.
- Recovery source `ass-membra/worklog.txt` existed with non-empty content and was used to restore.

## Impact

- Per-project TIMELOG evidence for `ÅSS: Membra` was missing from runs while the file was empty.
- This could reduce confidence in March attribution/reconciliation.

## Observed facts

- Empty file observed:
  - `$HOME/Workspace/Project/ass-membra/TIMELOG.md` (`0` bytes)
- Recoverable source found:
  - `$HOME/Workspace/Project/ass-membra/worklog.txt` (`4606` bytes)
- No committed `TIMELOG.md` history in that repo was available for direct git restore.

## Recovery actions

- Backed up current targets:
  - `$HOME/Workspace/Project/ass-membra/TIMELOG.md.backup.20260505-165015`
  - `$HOME/.gittan/worklogs/ass-membra.md.backup.20260505-165015`
- Restored:
  - copied `worklog.txt` -> `ass-membra/TIMELOG.md`
- Synced central store:
  - copied `worklog.txt` -> `~/.gittan/worklogs/ass-membra.md`

## Prevention steps

- Treat source worklogs as immutable during migration (copy/append only).
- Keep timestamped backup before any migration/sync write.
- Add a sanity check in migration tooling:
  - warn/fail when source is unexpectedly empty compared to previous non-empty state.
- Prefer central explicit project worklog paths in config:
  - `~/.gittan/worklogs/<project-id>.md`

## Follow-up

- Add optional migration guard mode (`--fail-on-empty-source`) for safer batch runs.
- Add a small validation command to list configured project worklogs with size and mtime.
