"""Shared CLI deprecation warnings."""

from __future__ import annotations

from rich.console import Console

URL_MAPPING_REPLACEMENT = "gittan review"
TRIAGE_MAP_REPLACEMENT = URL_MAPPING_REPLACEMENT  # backward-compatible alias


def warn_deprecated_command(
    command: str,
    *,
    replacement: str = TRIAGE_MAP_REPLACEMENT,
    extra: str | None = None,
) -> None:
    """Print a stderr deprecation notice; command continues unless caller exits."""
    message = (
        f"[yellow]Deprecated:[/yellow] `{command}` will be removed in a future release; "
        f"use `{replacement}` instead."
    )
    if extra:
        message = f"{message} {extra}"
    Console(stderr=True).print(message)
