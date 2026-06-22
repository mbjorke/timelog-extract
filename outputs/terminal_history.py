"""Historical column labels and legends for terminal report output."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from core.cli_status_history import HISTORY_LEGEND
from outputs.terminal_theme import STYLE_MUTED


def git_column_label(args: Any) -> str:
    if getattr(args, "history_source", False):
        return "Git estimate"
    return "Git only"


def print_history_legend(console: Console, args: Any) -> None:
    if not getattr(args, "history_source", False):
        return
    console.print(f"[{STYLE_MUTED}]{HISTORY_LEGEND}[/{STYLE_MUTED}]")
