"""Typer commands: configuration inspection utilities."""

from __future__ import annotations

import json

import typer

from core.cli_app import app
from core.config import resolve_projects_config_path_and_source

config_app = typer.Typer(help="Inspect active config paths.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("path")
def config_path(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output."),
):
    """Print active projects-config path and source."""
    resolved_path, source = resolve_projects_config_path_and_source()
    source_label = {
        "cwd": "repository-local file (current working directory)",
        "auto_profile_home": "fallback (automatic profile home ~/.gittan-<user>)",
        "GITTAN_HOME": "environment (GITTAN_HOME)",
        "GITTAN_PROJECTS_CONFIG": "environment (GITTAN_PROJECTS_CONFIG)",
    }.get(source, source)
    exists = resolved_path.is_file()

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "projects_config_path": str(resolved_path),
                    "source": source,
                    "source_label": source_label,
                    "exists": exists,
                }
            )
        )
        return

    typer.echo(f"projects_config_path={resolved_path}")
    typer.echo(f"source={source_label}")
    typer.echo(f"exists={'yes' if exists else 'no'}")
