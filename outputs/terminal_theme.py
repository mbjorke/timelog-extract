"""Shared terminal palette and icon semantics for CLI output."""

from __future__ import annotations

# Report palette
CLR_BERRY = "#9f7aff"
CLR_BERRY_BRIGHT = "#b79bff"
CLR_MUTED = "#aaa0c8"
CLR_DIM = "#847d9f"
CLR_TEXT_SOFT = "#d8d0ee"
CLR_GREEN = "#47cfa8"
CLR_SOURCE_BLUE = "#67a8ff"
CLR_VALUE_ORANGE = "#e7ad5a"

# Doctor/status semantic tokens
STYLE_LABEL = "#cfc8e8"
STYLE_MUTED = "#8f86ad"
STYLE_BORDER = "#4a4660"
OK_ICON = "[#47cfa8]✓[/#47cfa8]"
WARN_ICON = "[#d6b06a]![/#d6b06a]"
# Standardized icon set uses ! for failures/warnings.
FAIL_ICON = "[#e26d85]![/#e26d85]"
NA_ICON = f"[{STYLE_MUTED}]•[/{STYLE_MUTED}]"
