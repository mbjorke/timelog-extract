"""Discover git repo activity from Cursor logs (git --git-dir lines are report noise)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.git_project_bootstrap import build_repo_project_seed

_GIT_DIR_CMD_RE = re.compile(r">\s*git --git-dir\s+(\S+)", re.IGNORECASE)
_TS_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_TS_ISO_BRACKET_PATTERN = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?\]"
)


def _parse_cursor_log_ts(line: str, local_tz: Any) -> datetime | None:
    match = _TS_PATTERN.match(line)
    if match:
        try:
            # fromisoformat accepts space separators and is ~30x faster than strptime.
            return datetime.fromisoformat(match.group(1)).replace(tzinfo=local_tz)
        except ValueError:
            return None
    match = _TS_ISO_BRACKET_PATTERN.match(line)
    if not match:
        return None
    iso = (match.group(1) + (match.group(2) or "")).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed


def _repo_path_from_git_dir_arg(raw_arg: str) -> Path | None:
    raw = str(raw_arg or "").strip().strip("\"'")
    if not raw:
        return None
    path = Path(raw)
    if path.name == ".git":
        return path.parent
    if raw.endswith("/.git"):
        return Path(raw[: -len("/.git")])
    if (path / ".git").is_dir():
        return path
    if path.name == ".git" and path.parent.exists():
        return path.parent
    return None


def collect_git_command_slug_hits(
    home: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz: Any,
) -> dict[str, tuple[int, str]]:
    """Return github slug -> (hit_count, repo_folder_name) from Cursor git invocations."""
    logs_dir = home / "Library" / "Application Support" / "Cursor" / "logs"
    if not logs_dir.is_dir():
        return {}

    slug_hits: dict[str, tuple[int, str]] = {}
    for log_file in logs_dir.glob("**/*.log"):
        try:
            with open(log_file, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if "git --git-dir" not in line.lower():
                        continue
                    ts = _parse_cursor_log_ts(line, local_tz)
                    if ts is None or not (dt_from <= ts <= dt_to):
                        continue
                    match = _GIT_DIR_CMD_RE.search(line)
                    if not match:
                        continue
                    repo_path = _repo_path_from_git_dir_arg(match.group(1))
                    if repo_path is None:
                        continue
                    seed = build_repo_project_seed(repo_path)
                    if seed is None:
                        continue
                    slug = f"{seed.customer.lower()}/{seed.name.lower()}"
                    count, _label = slug_hits.get(slug, (0, repo_path.name))
                    slug_hits[slug] = (count + 1, repo_path.name)
        except OSError:
            continue
    return slug_hits
