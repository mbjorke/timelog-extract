## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-17 - [Check open PRs before a new Palette PR]
**Learning:** The same Palette brief (`sources` styling / UX) produced a long stack of open PRs (#375–#387) without checking whether yesterday’s PR already covered the work.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` before every Palette run — list open PRs, match on title/branch, and do not open a duplicate.
