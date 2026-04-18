"""Doctor source checking rows for GitHub and Toggl (extracted from cli_doctor_sources_projects.py)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich import markup
from rich.table import Table

from collectors.toggl import toggl_source_enabled
from outputs.terminal_theme import NA_ICON, OK_ICON, STYLE_MUTED


def add_github_doctor_row(table: Table, gh_mode: str, github_user: str | None) -> None:
    """Add GitHub source status row to doctor health check table."""
    gh_user = (github_user or os.getenv("GITHUB_USER") or "").strip()
    gh_token_present = bool((os.getenv("GITHUB_TOKEN") or "").strip())
    if gh_mode == "off":
        table.add_row(
            "GitHub Source",
            NA_ICON,
            f"[{STYLE_MUTED}]Disabled ({gh_mode}); enable with --github-source on[/{STYLE_MUTED}]",
        )
    elif not gh_user:
        table.add_row(
            "GitHub Source",
            NA_ICON,
            f"[{STYLE_MUTED}]Not configured ({gh_mode}); set --github-user or GITHUB_USER[/{STYLE_MUTED}]",
        )
    else:
        token_note = "token present" if gh_token_present else "no token (public API limits apply)"
        table.add_row(
            "GitHub Source",
            OK_ICON,
            f"[{STYLE_MUTED}]Enabled ({gh_mode}) for user '{gh_user}' — {token_note}[/{STYLE_MUTED}]",
        )


def add_toggl_doctor_row(table: Table, toggl_source: str) -> None:
    """Add Toggl source status row to doctor health check table."""
    toggl_enabled, toggl_reason = toggl_source_enabled(argparse.Namespace(toggl_source=toggl_source))
    toggl_token_present = bool((os.getenv("TOGGL_API_TOKEN") or "").strip())
    if toggl_enabled:
        token_note = "token present" if toggl_token_present else "no token"
        table.add_row(
            "Toggl Source",
            OK_ICON,
            f"[{STYLE_MUTED}]Enabled ({toggl_source}) — {token_note}[/{STYLE_MUTED}]",
        )
    else:
        escaped_reason = markup.escape(toggl_reason or "")
        table.add_row(
            "Toggl Source",
            NA_ICON,
            f"[{STYLE_MUTED}]Not configured ({toggl_source}); {escaped_reason}[/{STYLE_MUTED}]",
        )
