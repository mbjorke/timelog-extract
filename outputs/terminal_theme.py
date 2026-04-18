"""Shared terminal palette and icon semantics for CLI output."""

from __future__ import annotations

# Report palette — vibrant berry family, aligned with gittan.html :root (cousin to Blueberry Maybe / blueberry.ax).
# Void/background for “terminal” is #0a0714 on the site; CLI inherits these accents on the user’s terminal theme.
CLR_BERRY = "#d946ef"
CLR_BERRY_BRIGHT = "#f0abfc"
CLR_MUTED = "#c4b5fd"
CLR_DIM = "#a78bfa"
CLR_TEXT_SOFT = "#faf5ff"
CLR_GREEN = "#4ade80"
CLR_SOURCE_BLUE = "#60a5fa"
CLR_VALUE_ORANGE = "#fbbf24"

# Doctor/status semantic tokens
STYLE_LABEL = "#e9d5ff"
STYLE_MUTED = "#a78bfa"
STYLE_BORDER = "#6d28d9"
OK_ICON = f"[{CLR_GREEN}]✓[/{CLR_GREEN}]"
WARN_ICON = "[#f5a623]![/#f5a623]"
# Standardized icon set uses ! for failures/warnings.
FAIL_ICON = "[#e26d85]![/#e26d85]"
NA_ICON = f"[{STYLE_MUTED}]•[/{STYLE_MUTED}]"
