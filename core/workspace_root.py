"""Workspace root resolution helpers for CLI runtime."""

from __future__ import annotations

import subprocess
from pathlib import Path


def runtime_workspace_root(*, cwd: Path | None = None) -> Path:
    """Prefer git top-level for active workspace; fall back to cwd."""
    current = (cwd or Path.cwd()).resolve()
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(current),
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return current
    if completed.returncode == 0 and completed.stdout.strip():
        return Path(completed.stdout.strip()).resolve()
    return current
