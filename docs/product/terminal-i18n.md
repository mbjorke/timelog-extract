# English UI strings (i18n backlog)

User-facing output is being moved to **English** for consistency and tooling.

## Done

- `outputs/terminal.py` — report, source summary, session preview (including **one line per source** when space allows, then fill to 5 lines).
- `core/cli.py` — `--min-session`, `--exclude`, `--only-project` / `--customer` metavar/help (partial).
- `outputs/pdf.py` — invoice labels and generated fallback prose translated to English.
- `tests/test_pdf_labels.py` — regression guard for key PDF label constants.

## Remaining (translate in follow-up PRs)

| Area | File(s) | Notes |
|------|---------|--------|
| Utility scripts | `scripts/*.py` | Any user-visible strings |
| Tests | Tests that assert exact CLI help text | Update if help strings change |
| Docs | `README.md` if it quotes old Swedish output | Align examples |

## Session preview rule

When `--all-events` is off, each session prints up to **5** lines. The picker **first** adds one distinct `project \| detail` line per **source** (in `SOURCE_ORDER`), then fills remaining slots in time order. This keeps e.g. GitHub visible alongside Cursor in the same session.
