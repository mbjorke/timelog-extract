"""Small themed ASCII heroes for key CLI commands."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


_HEROES: dict[str, tuple[list[str], str]] = {
    "status": (
        [
            "+-------------------------------------------------------------------------+",
            "|  /\\_/\\   Gittan Status                                                  |",
            "| ( o.o )  Choose timeframe to get started.                               |",
            "|  > ^ <   Tip: run `gittan status --today` for a fast check.             |",
            "|          AI-assisted estimates: always verify before reporting/invoicing.|",
            "+-------------------------------------------------------------------------+",
        ],
        "Local timeline -> review-ready.",
    ),
    "doctor": (
        [
            "+-------------------------------------------------------------------------+",
            "|  /\\_/\\   Gittan Doctor                                                  |",
            "| ( O.O )  Quick health scan: sources, permissions, and config.           |",
            "|  > ^ <   Doctor tip: fix one warning at a time, then rerun doctor.      |",
            "|          Safety: doctor is read-only and will not modify project files. |",
            "+-------------------------------------------------------------------------+",
        ],
        "Diagnose first, then optimize.",
    ),
    "setup": (
        [
            "+-------------------------------------------------------------------------+",
            "|  /\\_/\\   Gittan Setup                                                   |",
            "| ( ^-^ )  Welcome! Guided onboarding for local-first timelog reporting.  |",
            "|  > u <   Setup tip: dry-run first when changing machine-wide settings.  |",
            "|          You approve prompts before any write operations run.           |",
            "+-------------------------------------------------------------------------+",
        ],
        "Calm setup, clear next steps.",
    ),
    "setup-global-timelog": (
        [
            "+-------------------------------------------------------------------------+",
            "|  /\\_/\\   Gittan Global Timelog                                          |",
            "| ( o.o )  Configure machine-wide commit -> TIMELOG automation.           |",
            "|  > ^ <   Tip: use --dry-run to preview hook and git config actions.     |",
            "|          Designed to be safe, explicit, and reversible.                 |",
            "+-------------------------------------------------------------------------+",
        ],
        "Global automation with local control.",
    ),
    "report": (
        [
            "+-------------------------------------------------------------------------+",
            "|  /\\_/\\   Gittan Report                                                  |",
            "| ( o.o )  Scanning local activity signals for timeline and sessions.     |",
            "|  > ^ <   Report tip: start with `--today --source-summary`.             |",
            "|          Output is estimate-oriented: review before sharing or invoicing.|",
            "+-------------------------------------------------------------------------+",
        ],
        "Collect, classify, summarize.",
    ),
}


def print_command_hero(console: Console, command: str) -> None:
    """Print a command-specific ASCII hero and one-line tagline."""
    lines, tagline = _HEROES.get(command, _HEROES["status"])
    console.print(Text("\n".join(lines), style=f"bold {STYLE_LABEL}"))
    console.print(f"[{STYLE_MUTED}]{tagline}[/{STYLE_MUTED}]")


def hero_commands() -> list[str]:
    """Return stable command keys with dedicated hero variants."""
    return list(_HEROES.keys())

