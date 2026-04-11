"""Interactive Questionary prompts for the CLI."""

from __future__ import annotations

from datetime import datetime, timedelta

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
