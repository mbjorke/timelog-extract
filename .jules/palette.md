## 2026-07-09 - Aligning `projects` command with UX guidelines
**Learning:** Commands that maintain an in-memory state (like interactive project management) can leave users uncertain about whether their changes are permanent. Explicit "Next:" guidance after memory-only updates is crucial for trustworthiness.
**Action:** Replaced ad-hoc colors with theme tokens/icons and added muted "Next: Select 'Save & Exit'..." hints to the `projects` command. Standardized the project list table with `box.ROUNDED` and shared theme tokens.

## 2026-07-16 - Aligning `sources` command table and actionability
**Learning:** Dense data summary commands like `sources` can easily drift into using ad-hoc rainbow colors that violate calm terminal aesthetics. Additionally, not providing a clear follow-up command for uncategorized entries leaves users without a clear path forward.
**Action:** Standardized the `sources` table with shared theme tokens (`STYLE_BORDER`, `STYLE_LABEL`, `CLR_SOURCE_BLUE`, `CLR_VALUE_ORANGE`, `STYLE_MUTED`, and `STYLE_DIM`). Implemented conditional "Next:" guidance recommending `gittan review` when uncategorized signals exist and `gittan report --today` when none exist.

## 2026-07-17 - Finish the PR after review comments are addressed
**Learning:** Palette kept opening new PRs for the same `sources` UX brief (#375–#387) instead of finishing the open one. Jules often has **no `gh` CLI** — merge via the GitHub UI (Squash and merge) if available; otherwise comment that the PR is ready to merge and stop. Leaving it open without a hand-off invites tomorrow’s duplicate; a stale tip squash-merged as #387 deleted unrelated `main` work.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` §5: fix review threads on the existing PR, sync with `main`, then merge in the GitHub UI **or** post a ready-to-merge comment. Do not open another Palette PR for the same outcome. Never land a tip that deletes files already on `main`.

## 2026-07-17 - Aligning `review` URL candidate table and cancel actions
**Learning:** Table components rendering dense text like URL candidates can feel unpolished without a clear boundary and semantic styles. Also, hardcoded colors like `[yellow]` break visual cohesion.
**Action:** Aligned `_render_candidates_table` in `core/cli_url_mapping.py` with standard `ROUNDED` box styling, `STYLE_BORDER`, and shared theme tokens. Replaced ad-hoc yellow highlights on cancellation with `CLR_VALUE_ORANGE`.

## 2026-07-18 - Standardize Interactive UX Cancellation Messages with Official Theme Accent
**Learning:** Hardcoded coloring like `[yellow]` inside interactive commands (e.g., `review` / URL mapping) violates the repository's terminal style guide, which mandates using official theme tokens (`CLR_VALUE_ORANGE`) instead of arbitrary colors for consistent accenting and palette compliance.
**Action:** Replaced ad-hoc `[yellow]` cancellation prints in `core/cli_url_mapping.py` and `core/mapping_review_flow.py` with the shared `CLR_VALUE_ORANGE` theme token, and updated imports accordingly.

## 2026-07-19 - Demoting expected-absence warnings in passive collectors
**Learning:** Hard-coded warning diagnostics from passive context collectors (like Apple Mail) on expected-absence systems (e.g., Linux or macOS without Mail) produce unnecessary clutter on every command run. When a source's mode is set to "auto" (default), missing dependencies or directories should quietly disable the source rather than issuing a warning alert.
**Action:** Changed Apple Mail collector registration to only enable the collector if `mail_source` is explicitly `"on"`, or if `mail_source` is `"auto"` and `mail_root` exists. This prevents expected-absence warning diagnostics from printing to stderr during routine command execution while still alerting when explicitly requested.

## 2026-07-20 - Non-interactive Timeframe Option Support for CLI Analysis Commands
**Learning:** Interactive commands like `sources` can be annoying and disrupt scripts/non-interactive environments when they force prompt-driven timeframe selections. Adding standard CLI timeframe flags and utilizing `resolve_date_window` with `prompt_if_missing` conditional flows delivers seamless, scriptable execution without breaking interactive convenience.
**Action:** Added standard timeframe options (`--from`, `--to`, `--today`, `--yesterday`, `--last-3-days`, `--last-week`, `--last-14-days`, `--last-month`) to the `sources` command in `core/cli_doctor_sources_projects.py`. Integrated `resolve_date_window(..., prompt_if_missing=...)` to bypass interactive prompting when flags are provided, and updated tests in `tests/test_cli_sources.py` accordingly.

## 2026-07-21 - Standardizing `evidence-check` Output with Theme Tokens and Icon Redundancy
**Learning:** Diagnostic checks like `evidence-check` can drift into plain, unstyled terminal text or hardcoded `[yellow]` or `[green]` strings that violate visual consistency with the official theme. Incorporating semantic Rich tags, standard theme tokens, and icon redundancy elevates trustworthiness and scannability.
**Action:** Refactored the output of `gittan evidence-check` to leverage standard tokens (`STYLE_LABEL`, `STYLE_MUTED`, `CLR_VALUE_ORANGE`, `CLR_GREEN`), added `WARN_ICON`/`OK_ICON` redundancy to warnings and status messages, and used standard `[/]` closing tags to ensure reliable Rich parsing.

## 2026-07-22 - Standardizing `reported` CLI Output and Empty States
**Learning:** Legacy commands often output plain unstyled text, which breaks terminal cohesive aesthetic and scannability. Applying standardized Rich table semantics (`box.ROUNDED`, `STYLE_BORDER`, and specific column styling) along with standardized orange headline (`CLR_VALUE_ORANGE`) and muted (`STYLE_MUTED`) instruction next-steps for empty states preserves user flow, actionability, and visual consistency across the entire CLI app.
**Action:** Redesigned the output of `gittan reported list` and empty states for both `reported list` and `reported review` in `core/cli_reported.py` with the official styling guidelines. Added a test suite `ReportedUXFormattingTests` in `tests/test_cli_reported.py` to prevent regressions.
