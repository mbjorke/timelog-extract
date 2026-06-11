"""Doctor source checking rows for GitHub and Toggl (extracted from cli_doctor_sources_projects.py)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from types import SimpleNamespace

from rich import markup
from rich.table import Table

from collectors.github import DEFAULT_GITHUB_API_BASE, resolve_github_api_base, resolve_github_usernames
from collectors.toggl import toggl_source_enabled
from core.setup_github_env import probe_gh_cli_auth
from outputs.terminal_theme import NA_ICON, OK_ICON, STYLE_MUTED, WARN_ICON


def _format_github_users(users: list[str]) -> str:
    if len(users) == 1:
        return f"user '{users[0]}'"
    shown = users[:3]
    tail = f", +{len(users) - 3} more" if len(users) > 3 else ""
    return f"{len(users)} users ({', '.join(shown)}{tail})"


def _github_api_base_warning(api_base: str) -> str:
    lowered = api_base.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return "; warning: GITHUB_API_BASE_URL should start with http:// or https://"
    is_default = api_base.rstrip("/") == DEFAULT_GITHUB_API_BASE.rstrip("/")
    if not is_default and "/api/v3" not in lowered:
        return "; warning: enterprise hosts usually need /api/v3"
    return ""


def add_github_doctor_row(table: Table, gh_mode: str, github_user: str | None) -> None:
    """
    Append a GitHub source status row to the provided doctor health-check table.
    
    Determines the effective GitHub user (from the explicit `github_user` argument or the
    `GITHUB_USER` environment variable) and whether a `GITHUB_TOKEN` is present, then adds
    one of three rows to `table`: disabled when `gh_mode` is "off", not configured when no
    user is available, or enabled for the resolved user with a note about token presence.
    
    Parameters:
        table (Table): The Rich table to append the status row to.
        gh_mode (str): The configured GitHub mode (e.g., "off" or "on"); "off" produces a disabled row.
        github_user (str | None): Optional explicit GitHub username to use instead of the `GITHUB_USER` env var.
    """
    gh_users = resolve_github_usernames(SimpleNamespace(github_user=github_user))
    gh_token_present = bool((os.getenv("GITHUB_TOKEN") or "").strip())
    api_base = resolve_github_api_base()
    api_note = ""
    if api_base.rstrip("/") != DEFAULT_GITHUB_API_BASE.rstrip("/"):
        api_note = f"; API {api_base}"
    warn_note = _github_api_base_warning(api_base)
    if gh_mode == "off":
        table.add_row(
            "GitHub Source",
            NA_ICON,
            f"[{STYLE_MUTED}]Disabled ({gh_mode}); enable with --github-source on[/{STYLE_MUTED}]",
        )
    elif not gh_users:
        table.add_row(
            "GitHub Source",
            NA_ICON,
            f"[{STYLE_MUTED}]Not configured ({gh_mode}); set --github-user or GITHUB_USER[/{STYLE_MUTED}]",
        )
    else:
        gh_cli = probe_gh_cli_auth()
        if gh_token_present:
            token_note = "token present"
        elif gh_cli.authenticated:
            token_note = (
                "no GITHUB_TOKEN env var (gh CLI authenticated — "
                "optional: export GITHUB_TOKEN=$(gh auth token))"
            )
        else:
            token_note = "no token (public API limits apply; run `gh auth login` for private repos)"
        user_note = _format_github_users(gh_users)
        table.add_row(
            "GitHub Source",
            OK_ICON,
            f"[{STYLE_MUTED}]Enabled ({gh_mode}) for {user_note} — {token_note}{api_note}{warn_note}[/{STYLE_MUTED}]",
        )


def add_gh_cli_doctor_row(table: Table) -> None:
    """Append GitHub CLI (`gh`) auth status — optional but needed for private repo discovery."""
    gh_cli = probe_gh_cli_auth()
    if not gh_cli.installed:
        table.add_row(
            "GitHub CLI (gh)",
            NA_ICON,
            f"[{STYLE_MUTED}]Not installed (optional) — `brew install gh` for private repo listing[/{STYLE_MUTED}]",
        )
        return
    if not gh_cli.authenticated:
        table.add_row(
            "GitHub CLI (gh)",
            WARN_ICON,
            f"[{STYLE_MUTED}]Installed but not logged in — run `gh auth login`[/{STYLE_MUTED}]",
        )
        return
    login_note = f" as {gh_cli.login}" if gh_cli.login else ""
    table.add_row(
        "GitHub CLI (gh)",
        OK_ICON,
        f"[{STYLE_MUTED}]Authenticated{login_note}[/{STYLE_MUTED}]",
    )


def add_toggl_doctor_row(table: Table, toggl_source: str) -> None:
    """
    Append a Toggl source status row to the provided doctor health-check table.
    
    Determines Toggl enablement by calling `toggl_source_enabled` with the given `toggl_source`, checks presence of the `TOGGL_API_TOKEN` environment variable, and adds a single row describing whether the Toggl source is enabled (including token presence) or not configured (including the escaped reason when available).
    
    Parameters:
        table (Table): A Rich Table to which the status row will be appended.
        toggl_source (str): Identifier/name of the Toggl source to display in the status text.
    """
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
