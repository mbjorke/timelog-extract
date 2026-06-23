"""Shared shell-profile helpers for credential env bootstrap.

Used by `setup_github_env` and `setup_integration_env` so every integration
persists secrets to the user's shell profile the same way.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path


def shell_profile_path() -> Path:
    """Best-effort path to the user's interactive shell profile."""
    shell = (os.environ.get("SHELL") or "").lower()
    home = Path.home()
    if "zsh" in shell:
        return home / ".zshrc"
    if "bash" in shell:
        return home / ".bashrc"
    return home / ".profile"


def upsert_export(path: Path, key: str, value: str, *, dry_run: bool) -> bool:
    """Insert or replace an `export KEY=value` line in the shell profile.

    Returns True when a change was made (or would be made in dry-run).
    """
    line = f"export {key}={shlex.quote(value)}"
    if dry_run:
        return True
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    rows = existing.splitlines()
    prefix = f"export {key}="
    changed = False
    found = False
    out: list[str] = []
    for row in rows:
        if row.strip().startswith(prefix):
            out.append(line)
            found = True
            changed = True
        else:
            out.append(row)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(line)
        changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed
