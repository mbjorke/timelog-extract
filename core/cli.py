"""CLI entry: Typer app, shared options, and command registration."""

from __future__ import annotations

import sys

import typer

# Side effect: register commands on `app`
from core import (
    cli_calendar_suggest,  # noqa: F401
    cli_cast,  # noqa: F401
    cli_config,  # noqa: F401
    cli_doctor_sources_projects,  # noqa: F401
    cli_evidence,  # noqa: F401
    cli_global_timelog_setup,  # noqa: F401
    cli_jira_sync,  # noqa: F401
    cli_map,  # noqa: F401
    cli_projects,  # noqa: F401
    cli_projects_audit,  # noqa: F401
    cli_report_status,  # noqa: F401
    cli_reported,  # noqa: F401
    cli_review,  # noqa: F401
    cli_search,  # noqa: F401
    cli_toggl_sync,  # noqa: F401
    cli_ux,  # noqa: F401
)
from core.cli_app import app
from core.cli_options import (
    TimelogRunOptions,
    as_run_options,
    package_version,
    split_comma_separated_list,
)

# Top-level options handled by Typer/the app itself — never redirect these into `report`.
_TOP_LEVEL_ONLY_OPTIONS = frozenset(
    {"--help", "-h", "--install-completion", "--show-completion", "--version", "-V"}
)


def redirect_legacy_report_argv(argv: list[str]) -> list[str]:
    """Rewrite legacy top-level report invocations to the `report` subcommand.

    Reporting moved under `report`, so a bare `--today` would dead-end with
    `No such option: --today` — a rough first command for a new user (tracked in
    docs/task-prompts/agent-inline-cli-ux-validation-task.md, GH-123). When the
    first argument is an option that is not a top-level-only flag, treat it as
    legacy report usage and insert `report`, so `… --today …` becomes
    `… report --today …`. Subcommands, bare invocation, the `--` end-of-options
    sentinel, and top-level-only options (`--help`, `--version`, …) pass through
    unchanged.
    """
    if (
        len(argv) >= 2
        and argv[1].startswith("-")
        and argv[1] != "--"  # end-of-options sentinel: leave for Typer (no_args_is_help)
        and argv[1] not in _TOP_LEVEL_ONLY_OPTIONS
    ):
        return [argv[0], "report", *argv[1:]]
    return argv


def main() -> None:
    """CLI entrypoint; handles top-level --version and legacy report flags before Typer."""
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        typer.echo(f"timelog-extract {package_version()}")
        raise SystemExit(0)
    redirected = redirect_legacy_report_argv(sys.argv)
    if redirected != sys.argv:
        # Teach the current contract without dead-ending; command-neutral so it holds
        # whether invoked as `gittan` or `python timelog_extract.py`. stderr keeps
        # JSON stdout clean.
        typer.echo(
            "Note: reporting now lives under the 'report' subcommand — running it for you. "
            "Next time, put 'report' before the flags.",
            err=True,
        )
        sys.argv = redirected
    app()


__all__ = [
    "TimelogRunOptions",
    "app",
    "as_run_options",
    "main",
    "package_version",
    "redirect_legacy_report_argv",
    "split_comma_separated_list",
]
