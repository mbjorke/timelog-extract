#!/usr/bin/env python3
"""Claude Code statusline: warn when the current project isn't set up in gittan.

S1 of the "gittan in the agent" slices
(`docs/task-prompts/gittan-statusline-task.md`): a cheap, collector-free
statusline. It resolves the current repo from the working directory and checks it
against `timelog_projects.json`; if no profile matches, it nudges you to
`gittan map`. No observed cache, no network — pure config + local git-remote read.

Wire it into Claude Code's `settings.json`:

    { "statusLine": { "type": "command",
      "command": "python3 <repo>/scripts/gittan_statusline.py" } }

The statusline runs on every prompt refresh, so this script is fully defensive:
any error prints an empty line rather than disrupting the prompt.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Run-from-anywhere: ensure the repo root is importable regardless of cwd.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

UNCATEGORIZED = "Uncategorized"
WARNING = "⚠ gittan: project not set up · gittan map"


def project_status(slug: str, profiles: list) -> str:
    """The statusline text for a resolved repo ``slug`` against ``profiles``.

    Pure (no git, no filesystem): empty when the path is not a git project
    (``slug == ""``) so we never warn outside a repo; the unconfigured warning
    when no profile matches; otherwise a quiet ``gittan: <project>`` confirmation.
    """
    if not slug:
        return ""
    from core.domain import classify_project

    project = classify_project(slug, profiles, UNCATEGORIZED)
    if project == UNCATEGORIZED:
        return WARNING
    return f"gittan: {project}"


def _resolve_cwd() -> str:
    """Current dir from Claude Code's statusline stdin JSON, else ``os.getcwd()``."""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
                cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd")
                if cwd:
                    return str(cwd)
    except (json.JSONDecodeError, ValueError, OSError):
        pass
    return os.getcwd()


def _load_profiles() -> list:
    """Load enabled project profiles from the resolved config (empty on any error)."""
    from core.config import (
        load_projects_config_payload,
        normalize_profile,
        resolve_projects_config_path,
    )

    path = resolve_projects_config_path()
    if not path.exists():
        return []
    payload = load_projects_config_payload(path)
    return [
        normalize_profile(p)
        for p in payload.get("projects", [])
        if isinstance(p, dict) and p.get("enabled", True)
    ]


def main() -> int:
    try:
        from core.repo_slug import resolve_path_repo_slug

        slug = resolve_path_repo_slug(_resolve_cwd())
        print(project_status(slug, _load_profiles()))
    except Exception:  # noqa: BLE001 - a statusline must never disrupt the prompt
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
