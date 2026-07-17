## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-16 - Aligning `sources` command table and actionability
**Learning:** Dense data summary commands like `sources` can easily drift into using ad-hoc rainbow colors that violate calm terminal aesthetics. Additionally, not providing a clear follow-up command for uncategorized entries leaves users without a clear path forward.
**Action:** Standardized the `sources` table with shared theme tokens (`STYLE_BORDER`, `STYLE_LABEL`, `CLR_SOURCE_BLUE`, `CLR_VALUE_ORANGE`, `STYLE_MUTED`, and `STYLE_DIM`). Implemented conditional "Next:" guidance recommending `gittan review` when uncategorized signals exist and `gittan report --today` when none exist.

## 2026-07-17 - Merge the PR after review comments are addressed
**Learning:** Palette kept opening new PRs for the same `sources` UX brief (#375–#387) instead of finishing the open one. When Qodo/CodeRabbit comments are fixed and CI is green, leaving the PR unmerged invites tomorrow’s run to duplicate it — and a stale tip squash-merged as #387 deleted unrelated `main` work.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` §5: fix review threads on the existing PR, sync with `main`, then `gh pr merge <N> --squash --delete-branch`. Do not open another Palette PR for the same outcome. Never merge a tip that deletes files already on `main`.
