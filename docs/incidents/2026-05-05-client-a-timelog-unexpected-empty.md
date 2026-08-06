# Incident: client-a TIMELOG unexpectedly empty

## Date

- 2026-05-05

## Summary

- `client-a/TIMELOG.md` was observed as `0` bytes even though prior workflow expected historical content.
- Recovery source `client-a/worklog.txt` existed with non-empty content and was used to restore.

## Impact

- Per-project TIMELOG evidence for `CLIENT A: LINE 2` was missing from runs while the file was empty.
- This could reduce confidence in March attribution/reconciliation.

## Observed facts

- Empty file observed:
  - `<workspace>/client-a/TIMELOG.md` (`0` bytes)
- Recoverable source found:
  - `<workspace>/client-a/worklog.txt` (`4606` bytes)
- No committed `TIMELOG.md` history in that repo was available for direct git restore.

## Recovery actions

- Backed up current targets:
  - `<workspace>/client-a/TIMELOG.md.backup.20260505-165015`
  - `~/.gittan/worklogs/client-a.md.backup.20260505-165015`
- Restored:
  - copied `worklog.txt` -> `client-a/TIMELOG.md`
- Synced central store:
  - copied `worklog.txt` -> `~/.gittan/worklogs/client-a.md`

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
