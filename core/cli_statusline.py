"""gittan statusline — the one-line agent statusline as a command.

Same line as ``scripts/gittan_statusline.py`` (project context + today's
unreported hours from the observed cache; no collectors, no network), reachable
through the installed ``gittan`` so a Claude Code ``statusLine`` setting or the
Claude Code plugin (``claude-code-plugin/``) needs no absolute script path.
Runbook: ``docs/runbooks/gittan-statusline.md``.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from core.cli_app import app


@app.command("statusline")
def statusline_cmd(
    cwd: Annotated[
        Optional[str],
        typer.Option(
            "--cwd",
            help="Directory to describe. Default: Claude Code's statusline stdin JSON, else the current directory.",
        ),
    ] = None,
) -> None:
    """Print the agent statusline: project match and today's unreported hours."""
    from scripts import gittan_statusline as statusline

    if cwd is None:
        statusline.main()
        return
    typer.echo(statusline.line_for(cwd))
