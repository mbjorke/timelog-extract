## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-14 - Standardizing the `sources` command UX
**Learning:** The `sources` command was a diagnostic "dead end" with hardcoded colors and no clear next steps. Aligning it with the hero system and adding conditional guidance (review vs report) makes the analysis actionable.
**Action:** Added the `sources` hero to `outputs/cli_heroes.py`. Themed the `sources` table in `core/cli_doctor_sources_projects.py` using `CLR_SOURCE_BLUE`, `CLR_VALUE_ORANGE`, and `STYLE_MUTED`. Added a `try-except` wrapper with standardized error and next-step patterns.
