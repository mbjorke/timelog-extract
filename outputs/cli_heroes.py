"""Small themed ASCII heroes for key CLI commands.

Art matches the bumblebee + berries metaphor in ``outputs/gittan_banner.py`` (75-char panels).
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


_HEROES: dict[str, tuple[list[str], str]] = {
    "status": (
        [
            "+-------------------------------------------------------------------------+",
            "|    __      Gittan Status                                                |",
            "|   /oo\\     Choose timeframe to get started.                             |",
            "|   \\__/     Tip: run `gittan status --today` for a fast check.           |",
            "|  o    o    Estimates: verify before reporting or invoicing.             |",
            "+-------------------------------------------------------------------------+",
        ],
        "Local timeline -> review-ready.",
    ),
    "doctor": (
        [
            "+-------------------------------------------------------------------------+",
            "|    __      Gittan Doctor                                                |",
            "|   /oo\\     Quick scan: sources, permissions, and config.                |",
            "|   \\__/     Fix one warning at a time, then rerun doctor.                |",
            "|  o    o    Read-only: does not modify project files.                    |",
            "+-------------------------------------------------------------------------+",
        ],
        "Diagnose first, then optimize.",
    ),
    "setup": (
        [
            "+-------------------------------------------------------------------------+",
            "|    __      Gittan Setup                                                 |",
            "|   /oo\\     Welcome: guided onboarding for local-first reporting.        |",
            "|   \\__/     Tip: `--dry-run` before machine-wide settings.               |",
            "|  o    o    You approve prompts before any write operations.             |",
            "+-------------------------------------------------------------------------+",
        ],
        "Calm setup, clear next steps.",
    ),
    "setup-global-timelog": (
        [
            "+-------------------------------------------------------------------------+",
            "|    __      Gittan Global Timelog                                        |",
            "|   /oo\\     Machine-wide commit -> TIMELOG.md automation.                |",
            "|   \\__/     Tip: `--dry-run` previews hooks and git config.              |",
            "|  o    o    Designed to be explicit, safe, and reversible.               |",
            "+-------------------------------------------------------------------------+",
        ],
        "Global automation with local control.",
    ),
    "report": (
        [
            "+-------------------------------------------------------------------------+",
            "|    __      Gittan Report                                                |",
            "|   /oo\\     Scanning local signals for timelines and sessions.           |",
            "|   \\__/     Tip: start with `--today --source-summary`.                  |",
            "|  o    o    Estimate-oriented: review before sharing or invoicing.       |",
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
