# Incident: project config backup gap

Date: 2026-04-13

## Summary

During manual scenario testing, `timelog_projects.json` was moved to a `.bak` filename and later not restored, resulting in fallback/minimal configuration and perceived reporting gaps.

## Impact

- Project classification quality dropped because the rich project mapping was unavailable.
- Time reporting appeared incomplete for the affected period.
- Recovery required manual retrieval from git history.

## Root cause

- Critical configuration (`timelog_projects.json`) was treated as disposable local state during testing.
- `.gitignore` made the file easy to lose silently across cleanup/worktree operations.
- Setup behavior previously focused on bootstrap convenience over recovery guarantees.

## Detection

- User noticed missing/incorrect project attribution in normal reporting flow.
- Review of branch and history confirmed `timelog_projects.json.bak` existed in commit history.

## Recovery

- Restored full config from `07311de:timelog_projects.json.bak`.
- Saved pre-restore minimal file as a timestamped local backup.
- Verified with `gittan doctor` that Project Config and Worklog sources were accessible.

## Corrective actions

Implemented in 0.2.2 line:

- Setup now creates timestamped backups before recreating malformed project config files.
- Regression tests added for valid-config keep and malformed-config backup/recreate.
- Documentation now states role split:
  - `TIMELOG.md` is a human-readable work journal.
  - `timelog_projects.json` is critical system config and should have external backup.

## Follow-up actions

- Move active user config storage toward `~/.gittan/` to reduce repo-local loss risk.
- Keep repo `timelog_projects.example.json` as template only.
- Add explicit export/import command path for user config in future release.
