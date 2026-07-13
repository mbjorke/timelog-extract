## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-13 - Standardizing `sources` command styling
**Learning:** Hardcoded Rich colors (`cyan`, `green`, `red`, `magenta`) in tables can create a "rainbow" effect that distracts from the data. Adhering to `terminal_theme` tokens ensures the CLI remains "calm" and visually consistent across all diagnostic tools.
**Action:** Replaced ad-hoc colors in `gittan sources` with `CLR_SOURCE_BLUE` for source names, `CLR_VALUE_ORANGE` for primary impact metrics, and `STYLE_MUTED`/`STYLE_DIM` for secondary counts and details. Updated the status spinner and footer to use themed styles.
