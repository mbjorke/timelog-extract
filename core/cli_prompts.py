"""Interactive Questionary prompts for the CLI."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import NoReturn

import questionary
import typer


def prompt_for_timeframe() -> dict:
    """Show an interactive timeframe picker."""
    choice = questionary.select(
        "Which timeframe do you want to report on?",
        choices=[
            "Today",
            "Yesterday",
            "Last 3 days",
            "Last 7 days",
            "Last 14 days",
            "Last month (30 days)",
            "Custom date...",
            "Custom range...",
            "Cancel",
        ],
    ).ask()

    if choice == "Cancel" or not choice:
        raise typer.Exit()

    now = datetime.now()
    end_d = now.date()
    end_s = end_d.isoformat()
    if choice == "Today":
        return {"today": True, "date_from": end_s, "date_to": end_s}
    if choice == "Yesterday":
        yest = (end_d - timedelta(days=1)).isoformat()
        return {"yesterday": True, "date_from": yest, "date_to": yest}
    if choice == "Last 3 days":
        start = (end_d - timedelta(days=2)).isoformat()
        return {"last_3_days": True, "date_from": start, "date_to": end_s}
    if choice == "Last 7 days":
        start = (end_d - timedelta(days=6)).isoformat()
        return {"last_week": True, "date_from": start, "date_to": end_s}
    if choice == "Last 14 days":
        start = (end_d - timedelta(days=13)).isoformat()
        return {"last_14_days": True, "date_from": start, "date_to": end_s}
    if choice == "Last month (30 days)":
        start = (end_d - timedelta(days=29)).isoformat()
        return {"last_month": True, "date_from": start, "date_to": end_s}

    if choice == "Custom date...":
        date_str = questionary.text("Enter date (YYYY-MM-DD):", default=now.strftime("%Y-%m-%d")).ask()
        if not date_str:
            raise typer.Exit()
        return {"date_from": date_str, "date_to": date_str}

    if choice == "Custom range...":
        start_str = questionary.text(
            "From date (YYYY-MM-DD):",
            default=(now - timedelta(days=30)).strftime("%Y-%m-%d"),
        ).ask()
        end_str = questionary.text("To date (YYYY-MM-DD):", default=now.strftime("%Y-%m-%d")).ask()
        if not start_str or not end_str:
            raise typer.Exit()
        return {"date_from": start_str, "date_to": end_str}

    return {}


def cancel_interactive(console, *, already_saved=False) -> NoReturn:
    """Report a Ctrl-C truthfully, then exit 130.

    Interactive review loops save as they go, so "cancelled" is not the same
    claim as "nothing was written". Telling the operator that config is
    untouched when a rule or project has already been persisted is worse than
    saying nothing: they go looking for work that is already done, or create a
    project that now exists (GH review on #480).

    ``already_saved`` may be a bool or a short phrase naming what landed; the
    phrase is preferred where the caller knows it, since "some changes" sends
    the operator back to diff the config themselves.
    """
    from outputs.terminal_theme import CLR_VALUE_ORANGE, STYLE_MUTED

    if not already_saved:
        console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
        raise typer.Exit(code=130)

    what = already_saved if isinstance(already_saved, str) else "Earlier changes in this run were"
    console.print(
        f"[{CLR_VALUE_ORANGE}]Cancelled — {what} already saved and kept.[/{CLR_VALUE_ORANGE}]\n"
        f"[{STYLE_MUTED}]Nothing after that point was applied. Re-run to continue from here.[/{STYLE_MUTED}]"
    )
    raise typer.Exit(code=130)
