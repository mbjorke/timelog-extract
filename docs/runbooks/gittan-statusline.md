# Runbook: gittan statusline in Claude Code

Show gittan's project awareness in the Claude Code statusline. S1 warns when the
current repo isn't set up in `timelog_projects.json` so you can fix it before time
goes uncategorized.

## Enable

Add to your Claude Code `settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /absolute/path/to/timelog-extract/scripts/gittan_statusline.py"
  }
}
```

Use the absolute path to your clone. The script reads the current directory from
the statusline's stdin JSON (`workspace.current_dir`), falling back to the
process cwd.

## What it shows

| Situation | Statusline |
| --- | --- |
| Repo matches a configured project | `gittan: <project>` |
| Repo has no matching profile | `⚠ gittan: project not set up · gittan map` |
| Not a git repo / no remote | _(blank — no false warnings)_ |

## How it works

Pure config + local git read — **no collectors, no network**, so it is cheap
enough to run on every prompt refresh:

1. Resolve the repo slug (`owner/repo`) from the git remote
   (`core/repo_slug.py::resolve_path_repo_slug`).
2. Match it against enabled profiles in `timelog_projects.json`
   (`core/domain.py::classify_project`).
3. Print the warning, the matched project, or nothing.

The script is fully defensive: any error prints a blank line rather than
disrupting the prompt.

## Roadmap

This is S1 of the "gittan in the agent" slices
(`docs/task-prompts/gittan-statusline-task.md`). S2 adds an unreported-time nudge
(`⏱ Nh unreported`) once the observed cache lands.
