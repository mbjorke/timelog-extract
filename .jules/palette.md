## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.
