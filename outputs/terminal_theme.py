"""Shared terminal palette and icon semantics for CLI output."""

from __future__ import annotations

# Berry family — vivid accents (cousin to Blueberry / blueberry.ax).
# Secondary lines use darker hues + Rich `dim` so they read as *lighter weight*, not washed-out pastel.
CLR_BERRY = "#d946ef"
CLR_BERRY_BRIGHT = "#f0abfc"
CLR_ACCENT = "#e879f9"

CLR_TEXT_SOFT = "#f3e8ff"
CLR_MUTED = "#b0a0d0"
CLR_DIM = "#7f6b96"

CLR_GREEN = "#4ade80"
CLR_SOURCE_BLUE = "#60a5fa"
CLR_VALUE_ORANGE = "#fbbf24"

# Tables / doctor: headers & labels
STYLE_LABEL = "#e879f9"
STYLE_MUTED = "#b0a0d0"
STYLE_BORDER = "#7c3aed"

# Tree guides, meta tails, taglines — dim = visually thinner on terminals
STYLE_DIM = "dim #8b7a9e"

OK_ICON = f"[bold {CLR_GREEN}]✓[/bold {CLR_GREEN}]"
WARN_ICON = f"[bold {CLR_VALUE_ORANGE}]![/bold {CLR_VALUE_ORANGE}]"
FAIL_ICON = "[bold #fb7185]![/bold #fb7185]"
NA_ICON = f"[{CLR_DIM}]•[/{CLR_DIM}]"
