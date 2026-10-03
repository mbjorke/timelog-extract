# Gittan for Claude Code

A Claude Code plugin (function hooks) that keeps gittan visible while you work:

- **Status line** — `gittan statusline` for the session's directory: the matched
  project and today's unreported hours, or `⚠ gittan: project not set up`.
  Refreshed at session start and after every turn. Cheap: no collectors run.
- **One nudge** — a toast, once per session, when the repo matches no project
  profile (`gittan map` fixes it).
- **`/gittan [today|yesterday|week]`** — hours per project from
  `gittan report --format json`.

Needs a `gittan` that has the `statusline` command (added with GH-582) on `PATH`, or its path set as the
plugin's *gittan executable* in `/config`.

## Load it

```bash
claude --plugin-dir /path/to/timelog-extract/claude-code-plugin
```

or name the folder in `CLAUDE_CODE_PLUGIN_DIRS` (see Claude Code's plugin docs).

## Develop

From the repo root:

```bash
claude plugin validate claude-code-plugin
claude plugin test claude-code-plugin
python3 scripts/build_claude_plugin_fixture.py   # regenerate tests/fixture.ts
```

`tests/fixture.ts` is generated, never hand-edited: the script runs the real
post-commit hook and the real CLI in a throwaway home. Spec:
`docs/task-prompts/claude-code-plugin-task.md` (GH-582).
