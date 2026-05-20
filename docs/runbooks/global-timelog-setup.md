# Global timelog setup (machine-wide)

**Canonical command:** `gittan setup-global-timelog`  
Use **`--dry-run`** first to preview changes.

This configures Git so commits can append to a per-repo timelog file via a global hook path, scoped to the repositories you choose (or all). Pair this with explicit per-project worklog paths in `timelog_projects.json` so your reporting model stays locked to central per-project files. It is the maintained reference for this feature — use it from onboarding, docs, and CLI output.

## Quick use

```bash
gittan setup-global-timelog --dry-run   # preview
gittan setup-global-timelog --yes       # apply
```

## Policy

- Do not commit local worklog files (including legacy `TIMELOG.md`) — they stay local (global gitignore / excludes as configured).
- Treat `timelog_projects.json` as critical local data; the CLI warns if you move it carelessly.
- Default behavior is automatic: the CLI resolves the canonical projects config from the Gittan home directory (or profile fallback when present). Cwd-local `timelog_projects.json` is not auto-selected (see `gittan config path`).
- `GITTAN_PROJECTS_CONFIG` (exact file) and `GITTAN_HOME` (directory containing `timelog_projects.json`) are optional overrides when you need custom paths.

## Recommended per-project worklog standard

Use one central directory for per-project history:

- `~/.gittan/worklogs/<project-id>.md`
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

Use `scripts/migrate_project_worklogs.py` to migrate from legacy repo-local `TIMELOG.md`
files into central per-project files.

Preview first:

```bash
python3 scripts/migrate_project_worklogs.py \
  --dry-run \
  --default-source-root "$HOME/Workspace/Project" \
  --mapping project-alpha \
  --mapping project-beta \
  --mapping timelog-extract
```

Apply:

```bash
python3 scripts/migrate_project_worklogs.py \
  --default-source-root "$HOME/Workspace/Project" \
  --mapping project-alpha \
  --mapping project-beta \
  --mapping timelog-extract
```

When `--mapping` lists a project name only, sources resolve under `--default-source-root` (default: current working directory). Set an explicit root if your repos live elsewhere.

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
