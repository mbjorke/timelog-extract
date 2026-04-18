# Terminal Style Guide

This guide defines the visual language for CLI output in `gittan` so styling stays consistent across commands (`report`, `doctor`, `setup`, future commands).

## Principles

- Keep the terminal output **calm and readable**.
- Prefer **semantic hierarchy** over decorative boxes and borders.
- Use **few colors**; color should communicate meaning, not decorate every token.
- Keep dense data (event lines, status tables) visually light.

## Typography semantics

Use these roles consistently:

- **Heading**: section titles and primary anchors.
- **Label**: field names and short category labels.
- **Body**: main readable content.
- **Meta**: secondary detail text, long tails, low-priority diagnostics.
- **Accent value**: key numeric outcomes (hours/totals).
- **Positive**: success/status ticks and time stamps where appropriate.

## Color semantics

Implementation: **`outputs/terminal_theme.py`** (canonical hex tokens). The site (`gittan.html`) may use a slightly brighter marketing palette; the **CLI defaults to softer lavender table chrome** so long sessions stay readable.

- **Base**: purple-neutral **lavender greys** — `STYLE_LABEL` (headers / first column), `CLR_TEXT_SOFT` (body), `STYLE_MUTED` / `STYLE_DIM` (details and tails). Avoid saturating every line with `CLR_BERRY` / `CLR_BERRY_BRIGHT`; reserve those for rare emphasis if needed.
- **Source names**: a single blue tone (`CLR_SOURCE_BLUE`) — no rainbow per tool.
- **Values**: muted orange (`CLR_VALUE_ORANGE`).
- **Time stamps / success ticks**: muted green (`CLR_GREEN`) — keep this the clearest non-neutral accent where status matters.
- **Details** (long event tails, doctor “Accessible”, etc.): `STYLE_MUTED` or `STYLE_DIM` so labels stay visually primary.

## Structural rules

- Default to **no panel chrome** for regular report sections.
- Avoid heavy table boxes unless they add clear value.
- Prefer `Table.grid(...)` for lightweight readouts.
- Minimize bracket noise like `[Source] [Project]` when color + spacing is enough.

## Do / Don't

- **Do** keep summary sections compact and scannable.
- **Do** tone down long diagnostic lines so important labels stand out.
- **Do** keep status icons simple (`✓`, `•`, `!`) where used.
- **Don't** assign unique saturated colors to every source/tool.
- **Don't** mix multiple unrelated accent colors in the same line.
- **Don't** reintroduce strong borders/background blocks without a semantic reason.
- **Don't** hardcode hex colors in command modules when `terminal_theme` already defines a token — use **`STYLE_LABEL`**, **`STYLE_MUTED`**, **`STYLE_BORDER`**, etc.

## Implementation touchpoints

- `outputs/terminal_theme.py` — **canonical hex tokens** for CLI (void for “terminal” on the site is **`#0a0714`**).
- `gittan.html` — marketing / demo terminal chrome (berry family; need not be a literal copy of every CLI hex).
- `outputs/terminal.py` (report rendering)
- `core/cli_doctor_sources_projects.py` (doctor table semantics)

When changing styles, validate with:

- `python3 -m unittest tests/test_cli_regression_smoke.py`
- a manual visual check on `gittan report --today` and `gittan doctor`
