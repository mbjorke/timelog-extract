"""Typer commands: UX helpers and hero previews."""

from __future__ import annotations

import typer

from core.cli_app import app
from outputs.cli_heroes import hero_commands, print_command_hero


@app.command("ux-heroes")
def ux_heroes():
    """Preview hero sections only for key CLI commands."""
    from rich.console import Console

    console = Console()
    for idx, key in enumerate(hero_commands()):
        if idx:
            console.print("")
        print_command_hero(console, key)

