"""CLI entry: Typer app, shared options, and command registration."""

from __future__ import annotations

import sys

import typer

from core.cli_app import app
from core.cli_options import (
    TimelogRunOptions,
    as_run_options,
    package_version,
    split_comma_separated_list,
)

# Side effect: register commands on `app`
from core import cli_doctor_sources_projects  # noqa: F401
from core import cli_global_timelog_setup  # noqa: F401
from core import cli_jira_sync  # noqa: F401
from core import cli_report_status  # noqa: F401
from core import cli_ab_rule_suggestions  # noqa: F401
from core import cli_review  # noqa: F401
from core import cli_triage  # noqa: F401
from core import cli_ux  # noqa: F401


def main() -> None:
    """CLI entrypoint; handles top-level --version before Typer (subcommands stay unchanged)."""
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        typer.echo(f"timelog-extract {package_version()}")
        raise SystemExit(0)
    app()


__all__ = [
    "TimelogRunOptions",
    "app",
    "as_run_options",
    "main",
    "package_version",
    "split_comma_separated_list",
]
