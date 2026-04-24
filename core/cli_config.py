"""Typer commands: configuration inspection utilities."""

from __future__ import annotations

from pathlib import Path

import typer

from core.cli_app import app
from core.config import resolve_projects_config_path_and_source

config_app = typer.Typer(help="Inspect active config paths.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("path")
def config_path():
    """Print active projects-config path and source."""
    resolved_path, source = resolve_projects_config_path_and_source()
    source_label = {
        "cwd": "fallback (current working directory)",
        "auto_profile_home": "automatic profile home (~/.gittan-<user>)",
        "GITTAN_HOME": "environment (GITTAN_HOME)",
        "GITTAN_PROJECTS_CONFIG": "environment (GITTAN_PROJECTS_CONFIG)",
    }.get(source, source)
    exists = "yes" if Path(resolved_path).is_file() else "no"

    typer.echo(f"projects_config_path={resolved_path}")
    typer.echo(f"source={source_label}")
    typer.echo(f"exists={exists}")
