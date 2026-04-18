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

- **Base palette** is purple/neutral.
- **Source names** use a single blue tone (avoid rainbow source coloring).
- **Values** use muted orange.
- **Time stamps** use muted green.
- **Details** (for example long event payload tails or doctor “Accessible”) should be muted/dim.

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

## Implementation touchpoints

- `outputs/terminal_theme.py` — **canonical hex tokens** for CLI (keep aligned with **`gittan.html` `:root`**; void for “terminal” is **`#0a0714`** on the site).
- `gittan.html` — marketing / demo terminal chrome (same berry family, more vibrant than a literal copy of blueberry.ax).
- `outputs/terminal.py` (report rendering)
- `core/cli_doctor_sources_projects.py` (doctor table semantics)

When changing styles, validate with:

- `python3 -m unittest tests/test_cli_regression_smoke.py`
- a manual visual check on `gittan report --today` and `gittan doctor`
