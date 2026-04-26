"""Shared terminal palette and icon semantics for CLI output.

These tokens mirror the public Gittan brand marks as closely as terminals allow:
honey for value and state, blueberry for active evidence, green for approval, and
muted cool neutrals for the local-first shell surface.
"""

from __future__ import annotations

# --- Core text (cool neutrals on dark shell) ---
CLR_BERRY = "#3c83f6"
CLR_BERRY_BRIGHT = "#67a8ff"
CLR_MUTED = "#9aa7b8"
CLR_DIM = "#667386"
CLR_TEXT_SOFT = "#edf4ff"

# --- Semantic accents (use sparingly) ---
CLR_GREEN = "#47cfa8"
CLR_SOURCE_BLUE = CLR_BERRY_BRIGHT
CLR_VALUE_ORANGE = "#f5cc47"

# --- Tables: doctor / status / setup (shared column semantics) ---
# Label = headers & first column; Muted = details / long tails (see style guide).
STYLE_LABEL = "#d7e5f8"
STYLE_MUTED = CLR_MUTED
STYLE_BORDER = "#2a3444"

# Tree meta, taglines — Rich dim reads lighter without extra neon.
STYLE_DIM = f"dim {CLR_DIM}"

# Back-compat names (prefer roles above in new code)
CLR_ACCENT = CLR_BERRY_BRIGHT

OK_ICON = f"[{CLR_GREEN}]✓[/{CLR_GREEN}]"
WARN_ICON = f"[{CLR_VALUE_ORANGE}]![/{CLR_VALUE_ORANGE}]"
FAIL_ICON = "[#e26d85]![/#e26d85]"
NA_ICON = f"[{STYLE_MUTED}]•[/{STYLE_MUTED}]"
