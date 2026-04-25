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

## Historical detail

Older manual steps and narrative live in [`../legacy/global-timelog-automation-legacy.md`](../legacy/global-timelog-automation-legacy.md) (not updated with every CLI change).
