"""Typer application instance and global callback."""

from __future__ import annotations

import typer

app = typer.Typer(help="Gittan: Local activity aggregator for timereporting", no_args_is_help=True)


@app.callback()
def common(ctx: typer.Context):
    """Gittan: Aggregate work time from multiple local sources."""
    pass
