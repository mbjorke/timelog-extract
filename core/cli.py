"""CLI entry: Typer app, shared options, and command registration."""

from __future__ import annotations

import sys

import typer

# Side effect: register commands on `app`
from core import (
    cli_calendar_suggest,  # noqa: F401
    cli_capture,  # noqa: F401
    cli_cast,  # noqa: F401
    cli_config,  # noqa: F401
    cli_doctor_sources_projects,  # noqa: F401
    cli_evidence,  # noqa: F401
    cli_global_timelog_setup,  # noqa: F401
    cli_intent,  # noqa: F401
    cli_jira_sync,  # noqa: F401
    cli_map,  # noqa: F401
    cli_projects,  # noqa: F401
    cli_projects_audit,  # noqa: F401
    cli_report_status,  # noqa: F401
    cli_reported,  # noqa: F401
    cli_review,  # noqa: F401
    cli_search,  # noqa: F401
    cli_sources,  # noqa: F401
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
from core.config import GittanHomeError, gittan_data_dir

# Top-level options handled by Typer/the app itself — never redirect these into `report`.
_TOP_LEVEL_ONLY_OPTIONS = frozenset(
    {"--help", "-h", "--install-completion", "--show-completion", "--version", "-V", "-v"}
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
    # -v as well as -V: the installer's own remediation text tells the user to run
    # `gittan -V`, and lowercase is what most people type first. Rejecting it with
    # "No such option" at the exact moment someone is checking whether an upgrade
    # landed is a bad first impression for a one-character difference (GH-525).
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V", "-v"):
        typer.echo(f"timelog-extract {package_version()}")
        raise SystemExit(0)
    # Refuse a malformed $GITTAN_HOME once, up front, rather than partway through
    # a command. Nothing has been read or written yet, so there is no half-done
    # state to explain — and every command shares the check instead of each store
    # discovering it separately.
    try:
        gittan_data_dir()
    except GittanHomeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(2) from exc
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
    try:
        app()
    except GittanHomeError as exc:
        # A malformed data dir is a config mistake, not a crash. Exit before any
        # store is touched rather than guessing where the data belongs.
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(2) from exc


__all__ = [
    "TimelogRunOptions",
    "app",
    "as_run_options",
    "main",
    "package_version",
    "redirect_legacy_report_argv",
    "split_comma_separated_list",
]
