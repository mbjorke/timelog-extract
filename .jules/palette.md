## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-15 - Standardizing `sources` command and timeframe flags
**Learning:** The `sources` command was an outlier using a purely interactive timeframe picker and ad-hoc colors. Bringing it into parity with `status`/`report` flags makes the CLI more predictable and scriptable.
**Action:** Added standard date flags (`--today`, `--from`, etc.) to `gittan sources` and updated its table/empty-state output to use shared `terminal_theme` tokens.
