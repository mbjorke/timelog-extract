"""Shared terminal palette and icon semantics for CLI output.

Canonical roles are defined in ``docs/product/terminal-style-guide.md``.
Keep tokens aligned with the guide: calm hierarchy, few saturated accents, semantic color only.
"""

from __future__ import annotations

# --- Core text (lavender / neutral on void #0a0714) ---
CLR_BERRY = "#9f7aff"
CLR_BERRY_BRIGHT = "#b79bff"
CLR_MUTED = "#aaa0c8"
CLR_DIM = "#847d9f"
CLR_TEXT_SOFT = "#d8d0ee"

# --- Semantic accents (use sparingly) ---
CLR_GREEN = "#47cfa8"
CLR_SOURCE_BLUE = "#67a8ff"
CLR_VALUE_ORANGE = "#e7ad5a"

# --- Tables: doctor / status / setup (shared column semantics) ---
# Label = headers & first column; Muted = details / long tails (see style guide).
STYLE_LABEL = "#cfc8e8"
STYLE_MUTED = "#8f86ad"
STYLE_BORDER = "#4a4660"

# Tree meta, taglines — Rich dim reads lighter without extra neon.
STYLE_DIM = f"dim {CLR_DIM}"

# Back-compat names (prefer roles above in new code)
CLR_ACCENT = CLR_BERRY_BRIGHT

OK_ICON = f"[{CLR_GREEN}]✓[/{CLR_GREEN}]"
WARN_ICON = f"[{CLR_VALUE_ORANGE}]![/{CLR_VALUE_ORANGE}]"
FAIL_ICON = "[#e26d85]![/#e26d85]"
NA_ICON = f"[{STYLE_MUTED}]•[/{STYLE_MUTED}]"
