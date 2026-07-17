## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-16 - Aligning `sources` command table and actionability
**Learning:** Dense data summary commands like `sources` can easily drift into using ad-hoc rainbow colors that violate calm terminal aesthetics. Additionally, not providing a clear follow-up command for uncategorized entries leaves users without a clear path forward.
**Action:** Standardized the `sources` table with shared theme tokens (`STYLE_BORDER`, `STYLE_LABEL`, `CLR_SOURCE_BLUE`, `CLR_VALUE_ORANGE`, `STYLE_MUTED`, and `STYLE_DIM`). Implemented conditional "Next:" guidance recommending `gittan review` when uncategorized signals exist and `gittan report --today` when none exist.
