"""Typer application instance and global callback."""

from __future__ import annotations

import typer

app = typer.Typer(help="Gittan: Local-first CLI for reviewable project-hour evidence.", no_args_is_help=True)


@app.callback()
def common(ctx: typer.Context):
    """Aggregate local work signals into reviewable evidence before approval."""
    pass
