## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-16 - Aligning `sources` command table and actionability
**Learning:** Dense data summary commands like `sources` can easily drift into using ad-hoc rainbow colors that violate calm terminal aesthetics. Additionally, not providing a clear follow-up command for uncategorized entries leaves users without a clear path forward.
**Action:** Standardized the `sources` table with shared theme tokens (`STYLE_BORDER`, `STYLE_LABEL`, `CLR_SOURCE_BLUE`, `CLR_VALUE_ORANGE`, `STYLE_MUTED`, and `STYLE_DIM`). Implemented conditional "Next:" guidance recommending `gittan review` when uncategorized signals exist and `gittan report --today` when none exist.

## 2026-07-17 - Finish the PR after review comments are addressed
**Learning:** Palette kept opening new PRs for the same `sources` UX brief (#375–#387) instead of finishing the open one. Jules often has **no `gh` CLI** — merge via the GitHub UI (Squash and merge) if available; otherwise comment that the PR is ready to merge and stop. Leaving it open without a hand-off invites tomorrow’s duplicate; a stale tip squash-merged as #387 deleted unrelated `main` work.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` §5: fix review threads on the existing PR, sync with `main`, then merge in the GitHub UI **or** post a ready-to-merge comment. Do not open another Palette PR for the same outcome. Never land a tip that deletes files already on `main`.

## 2026-07-18 - Standardize Interactive UX Cancellation Messages with Official Theme Accent
**Learning:** Hardcoded coloring like `[yellow]` inside interactive commands (e.g., `review` / URL mapping) violates the repository's terminal style guide, which mandates using official theme tokens (`CLR_VALUE_ORANGE`) instead of arbitrary colors for consistent accenting and palette compliance.
**Action:** Replaced ad-hoc `[yellow]` cancellation prints in `core/cli_url_mapping.py` and `core/mapping_review_flow.py` with the shared `CLR_VALUE_ORANGE` theme token, and updated imports accordingly.
