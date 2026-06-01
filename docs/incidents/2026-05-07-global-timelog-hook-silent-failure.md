# Incident: global post-commit timelog hook silent failure

Date: 2026-05-07 (introduced) · detected 2026-06-01

## Summary

A regression in the embedded `post-commit` hook script caused **every commit** to exit early under `set -u` without appending worklog lines. Users who rely on `gittan setup-global-timelog` saw **no new TIMELOG entries** after the broken hook was installed, while git commits succeeded normally.

## Impact

- **Automatic commit → worklog** stopped (silent; no hook error surfaced to the user during `git commit`).
- Gaps in `TIMELOG.md` / `~/.gittan/worklogs/*.md` for the affected period.
- `gittan report` still showed Chrome/Cursor/Mail — **under-reporting** was easy to misread as “Gittan stopped tracking project X” rather than “hook died”.
- Recovery: re-run `gittan setup-global-timelog --yes` after fix, optional `git log` backfill into worklog (manual or script).

## Root cause

Two zsh issues in `core/global_timelog_hook_script.py` (`HOOK_BODY`), deployed to `~/.githooks/post-commit` on setup:

1. **`root_canon` used before assignment** — `REPO_HASH` referenced `$root_canon` above `root_canon="${ROOT_DIR:A}"`.
2. **Awk in double quotes** — `awk "{print substr($1,1,8)}"` made zsh expand `$1` (unset positional param) → `parameter not set` with `set -u`.

Both fail under `set -euo pipefail`; the hook exits before appending.

## Detection

- Last successful auto-logged commit timestamp aligned with last hook file mtime before regression.
- Manual run: `~/.githooks/post-commit` → `root_canon: parameter not set` / `awk … $1: parameter not set`.
- Commits after 2026-05-07 with zero matching worklog headings.

## Fix

- Move `home_canon` / `root_canon` before `REPO_HASH`.
- Use `awk '{print substr($1,1,8)}'` (single-quoted awk program).
- Static tests: definition order, awk quoting, optional macOS zsh smoke (see `tests/test_global_timelog_hook_script.py`).

After merge: users should run `gittan setup-global-timelog --yes` to refresh `~/.githooks/post-commit`.

## Corrective actions (this PR)

- Code fix in `core/global_timelog_hook_script.py`.
- Regression tests in `tests/test_global_timelog_hook_script.py`.
- This incident note + link from `docs/runbooks/global-timelog-setup.md`.

## Follow-up

- Consider a `gittan doctor` check that validates installed hook hash or embedded marker version.
- Document backfill pattern for hook outage windows (no automatic backfill in product yet).
