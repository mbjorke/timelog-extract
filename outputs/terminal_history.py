"""Historical column labels and legends for terminal report output."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from outputs.terminal_theme import STYLE_MUTED


def git_column_label(args: Any) -> str:
    if getattr(args, "history_source", False):
        return "Git estimate (all-time)"
    return "Git only"


def print_history_legend(console: Console, args: Any, *, show_totals: bool, show_git: bool) -> None:
    if not getattr(args, "history_source", False) or not (show_totals or show_git):
        return
    console.print(
        f"[{STYLE_MUTED}]Historical columns are display-only estimates — "
        f"TIMELOG sums worklog entries; Git derives from commit timestamps. "
        f"They do not change period Hours or billable totals.[/{STYLE_MUTED}]"
    )
