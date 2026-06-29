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
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Run-from-anywhere: ensure the repo root is importable regardless of cwd.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

UNCATEGORIZED = "Uncategorized"
WARNING = "⚠ gittan: project not set up · gittan map"
# A project+day is "handled" once you've confirmed, edited, or explicitly
# dismissed it — only un-acted-on observed time counts as unreported.
HANDLED_STATES = {"confirmed", "edited", "dismissed"}


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


def unreported_hours(project: str, day: str, home: "Path | None" = None) -> float:
    """Observed minus handled hours for ``(project, day)`` — the actionable backlog.

    Reads two fast JSONL stores (no collectors): the observed cache (Part A) and
    the reported store. ``handled`` = confirmed/edited/dismissed reported time.
    """
    from core.observed_cache import observed_hours_by_project_day
    from core.reported_time import reported_hours_by_project_day

    observed = observed_hours_by_project_day(home).get((project, day), 0.0)
    handled = reported_hours_by_project_day(home, states=HANDLED_STATES).get((project, day), 0.0)
    return max(0.0, observed - handled)


def statusline_text(slug: str, profiles: list, today: str, home: "Path | None" = None) -> str:
    """Full statusline: S1 project context + S2 unreported-time nudge.

    Unconfigured/non-git cases fall back to the S1 line. For a configured project
    it appends today's unreported hours (``⏱ Nh unreported``) or a quiet all-clear.
    """
    base = project_status(slug, profiles)
    if not base or base == WARNING:
        return base
    from core.domain import classify_project

    project = classify_project(slug, profiles, UNCATEGORIZED)
    hours = unreported_hours(project, today, home)
    if hours <= 0:
        return f"{base} · ✓ all reported today"
    return f"{base} · ⏱ {hours:.1f}h unreported · gittan reported"


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


def _load_profiles(cwd: str) -> list:
    """Load enabled project profiles for ``cwd``'s workspace (empty on any error).

    Resolves the config from the same directory we classify the repo against, so a
    statusline running outside the process cwd reads the right config.
    """
    from core.config import (
        load_projects_config_payload,
        normalize_profile,
        resolve_projects_config_path,
    )

    path = resolve_projects_config_path(Path(cwd))
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

        cwd = _resolve_cwd()
        slug = resolve_path_repo_slug(cwd)
        print(statusline_text(slug, _load_profiles(cwd), date.today().isoformat()))
    except Exception:  # noqa: BLE001 - a statusline must never disrupt the prompt
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
