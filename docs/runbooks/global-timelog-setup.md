# Global timelog setup (machine-wide)

**Canonical command:** `gittan setup-global-timelog`  
Use **`--dry-run`** first to preview changes.

This configures Git so commits can append to a repo-local `TIMELOG.md` via a global hook path, scoped to the repositories you choose (or all). It is the maintained reference for this feature — use it from onboarding, docs, and CLI output.

## Quick use

```bash
gittan setup-global-timelog --dry-run   # preview
gittan setup-global-timelog --yes       # apply
```

## Policy

- Do not commit `TIMELOG.md` — it stays local (global gitignore / excludes as configured).
- Treat `timelog_projects.json` as critical local data; the CLI warns if you move it carelessly.
- Default behavior is automatic: if no env vars are set and no repo-local config exists, the CLI uses `~/.gittan-<user>/timelog_projects.json`.
- `GITTAN_PROJECTS_CONFIG` (exact file) and `GITTAN_HOME` (directory containing `timelog_projects.json`) are optional overrides when you need custom paths.

## Recommended per-project worklog standard

Use one central directory for per-project history:

- `~/.gittan/worklogs/<project>.md`
- Keep source repo files in place during migration; copy/append instead of move/delete.
- Add each project worklog path in `timelog_projects.json` as profile-level `worklog`.

Example profile fragment:

```json
{
  "name": "timelog-extract",
  "worklog": "~/.gittan/worklogs/timelog-extract.md"
}
```

## Migration helper script (safe + idempotent)

Use `scripts/migrate_project_worklogs.py` to migrate from repo-local `TIMELOG.md`
files into central per-project files.

Preview first:

```bash
python3 scripts/migrate_project_worklogs.py \
  --dry-run \
  --mapping ass-membra \
  --mapping financing-portal \
  --mapping timelog-extract
```

Apply:

```bash
python3 scripts/migrate_project_worklogs.py \
  --mapping ass-membra \
  --mapping financing-portal \
  --mapping timelog-extract
```

Script behavior:

- creates `~/.gittan/worklogs/` when needed,
- keeps source files unchanged,
- creates timestamped destination backups before append updates,
- detects already-migrated content using a hash marker (idempotent reruns),
- reports missing/empty sources without crashing.

## Verification flow

1. Confirm destination files:
  - `ls -l ~/.gittan/worklogs`
2. Run at least one audit with JSON output and inspect timelog evidence:
  - `gittan projects-audit --json --last-14-days --screen-time off`
3. In the JSON output, verify each audited project shows expected timelog evidence
   in `evidence` / source fields for migrated worklog paths.

## Historical detail

Older manual steps and narrative live in [`../legacy/global-timelog-automation-legacy.md`](../legacy/global-timelog-automation-legacy.md) (not updated with every CLI change).
