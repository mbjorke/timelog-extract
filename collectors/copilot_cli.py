"""GitHub Copilot CLI local artifacts (~/.copilot or COPILOT_HOME).

Parses timestamp-like tokens from recent ``logs/*.log`` files. Best-effort only;
missing or unreadable data never raises.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

SOURCE = "GitHub Copilot CLI"
_TS = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?)"
)


def copilot_cli_data_dir(home: Path) -> Path:
    raw = (os.environ.get("COPILOT_HOME") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return home.expanduser() / ".copilot"


def _parse_ts(token: str) -> datetime | None:
    piece = token.strip().replace(" ", "T", 1)
    if piece.endswith("Z"):
        piece = piece[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(piece)
    except ValueError:
        return None


def collect_copilot_cli(
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    home: Path,
    classify_project: Callable[..., str],
    make_event: Callable[..., Dict[str, Any]],
) -> List[Dict[str, Any]]:
    logs = copilot_cli_data_dir(home) / "logs"
    if not logs.is_dir():
        return []
    results: List[Dict[str, Any]] = []
    seen: set[Tuple[datetime, str, str]] = set()
    tail = 256 * 1024
    candidates: List[Tuple[float, Path]] = []
    for path in logs.glob("*.log"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    paths = [path for _mtime, path in sorted(candidates, reverse=True)[:40]]
    for path in paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > tail:
            data = data[-tail:]
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if len(line) > 4000:
                line = line[:4000]
            for match in _TS.finditer(line):
                token = match.group("ts")
                ts = _parse_ts(token)
                if ts is None:
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt_from.tzinfo)
                if not (dt_from <= ts <= dt_to):
                    continue
                detail = line.strip()
                if len(detail) > 140:
                    detail = detail[:137] + "…"
                hay = f"{path.name} {detail}"
                project = classify_project(hay, profiles)
                key = (ts.replace(microsecond=0), detail[:80], project)
                if key in seen:
                    continue
                seen.add(key)
                results.append(make_event(SOURCE, ts, detail or SOURCE, project))
                if len(results) >= 2000:
                    return results
    return results
