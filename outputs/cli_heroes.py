"""Small themed heroes for key CLI commands."""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_GREEN,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
    STYLE_BORDER,
    STYLE_LABEL,
    STYLE_MUTED,
)


_HEROES: dict[str, tuple[list[str], str]] = {
    "status": (
        [
            "    __      Gittan Status",
            "   /oo\\     Local traces become review-ready evidence.",
            "   \\__/     Use --additive when project totals must reconcile.",
            "  o    o    Estimates stay local until you approve them.",
        ],
        "local timeline -> review-ready evidence",
    ),
    "doctor": (
        [
            "    __      Gittan Doctor",
            "   /oo\\     Checks source access, permissions, and config.",
            "   \\__/     Warnings are evidence gaps, not failures.",
            "  o    o    Read-only: nothing is changed on your machine.",
        ],
        "diagnose first, then approve fixes",
    ),
    "setup": (
        [
            "    __      Gittan Setup",
            "   /oo\\     Build a local project map from existing traces.",
            "   \\__/     Use --dry-run before machine-wide settings.",
            "  o    o    Every write is explicit and reviewable.",
        ],
        "local setup with clear approval points",
    ),
    "setup-global-timelog": (
        [
            "    __      Gittan Global Timelog",
            "   /oo\\     Machine-wide commits can feed a local worklog.",
            "   \\__/     --dry-run previews hooks and git config.",
            "  o    o    Automation stays explicit and reversible.",
        ],
        "global capture with local control",
    ),
    "report": (
        [
            "    __      Gittan Report",
            "   /oo\\     Turns local signals into a project-hour narrative.",
            "   \\__/     Add --project and --noise-profile to inspect totals.",
            "  o    o    Review before sharing, syncing, or invoicing.",
        ],
        "collect -> classify -> summarize",
    ),
}


def print_command_hero(console: Console, command: str) -> None:
    """Print a command-specific ASCII hero and one-line tagline."""
    lines, tagline = _HEROES.get(command, _HEROES["status"])
    hero = Text()
    for idx, line in enumerate(lines):
        if idx:
            hero.append("\n")
        if idx == 0:
            mark, title = line[:12], line[12:]
            hero.append(mark, style=f"bold {CLR_VALUE_ORANGE}")
            hero.append(title, style=f"bold {CLR_TEXT_SOFT}")
        else:
            mark, body = line[:12], line[12:]
            hero.append(mark, style=CLR_VALUE_ORANGE)
            hero.append(body, style=STYLE_LABEL)

    state_line = Text.assemble(
        ("observed", CLR_BERRY_BRIGHT),
        (" -> ", STYLE_MUTED),
        ("classified", CLR_VALUE_ORANGE),
        (" -> ", STYLE_MUTED),
        ("approved", CLR_GREEN),
    )
    console.print(
        Panel(
            Group(hero, Text(tagline, style=STYLE_MUTED), state_line),
            border_style=STYLE_BORDER,
            padding=(1, 2),
        )
    )


def hero_commands() -> list[str]:
    """Return stable command keys with dedicated hero variants."""
    return list(_HEROES.keys())
