"""VS Code chat-session evidence (stock Code / Insiders).

Stock VS Code application-support *logs* barely mention workspace paths — unlike
Cursor, which floods logs from proprietary extensions. The durable shared signal
is ``User/workspaceStorage/<id>/chatSessions/*.jsonl`` (VS Code chat / Copilot):
creation + per-request timestamps mapped to the workspace folder.

Detail lines never include prompt or response text.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List
from urllib.parse import unquote, urlparse

from collectors.vscode_fork import load_fork_workspaces
from core.repo_slug import path_attribution_anchor

logger = logging.getLogger(__name__)

SOURCE_NAME = "VS Code"
_VSCODE_APP_DIRS = ("Code", "Code - Insiders")
_TITLE_MAX = 60
_DETAIL_MAX = 90


def _base_dirs(home: Path) -> list[Path]:
    support = home / "Library" / "Application Support"
    return [support / name for name in _VSCODE_APP_DIRS]


def _ms_to_local(ms: Any, local_tz) -> datetime | None:
    try:
        value = float(ms)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # Values may be seconds or milliseconds.
    if value < 1e12:
        value *= 1000.0
    try:
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).astimezone(local_tz)
    except (OSError, OverflowError, ValueError):
        return None


def _folder_from_workspace_json(ws_dir: Path) -> str | None:
    path = ws_dir / "workspace.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw_uri = data.get("folder") or data.get("workspace")
    if not raw_uri:
        return None
    parsed = urlparse(str(raw_uri))
    return unquote(parsed.path) if parsed.scheme == "file" else str(raw_uri)


def _safe_title(raw: Any) -> str:
    text = " ".join(str(raw or "").split()).strip()
    if not text:
        return "Chat"
    if len(text) > _TITLE_MAX:
        return text[: _TITLE_MAX - 1] + "…"
    return text


def _events_from_chat_jsonl(
    path: Path,
    *,
    folder: str,
    profiles,
    dt_from,
    dt_to,
    local_tz,
    classify_project,
    make_event,
) -> List[dict]:
    """Emit one event per chat request (or session create) inside the window."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.debug("Could not read VS Code chat session %s: %s", path, exc)
        return []

    header: dict | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == 0 and isinstance(row.get("v"), dict):
            header = row["v"]
            break
    if not header:
        return []

    title = _safe_title(header.get("customTitle"))
    leaf = Path(folder).name
    hay = f"{folder} {title}"
    project = classify_project(hay, profiles)
    anchors = path_attribution_anchor(folder)
    out: List[dict] = []

    requests = header.get("requests")
    stamps: list[Any] = []
    if isinstance(requests, list):
        for req in requests:
            if isinstance(req, dict) and req.get("timestamp") is not None:
                stamps.append(req.get("timestamp"))
    if not stamps and header.get("creationDate") is not None:
        stamps.append(header.get("creationDate"))

    for stamp in stamps:
        ts = _ms_to_local(stamp, local_tz)
        if not ts or not (dt_from <= ts <= dt_to):
            continue
        detail = f"{leaf} — Copilot chat: {title}"[:_DETAIL_MAX]
        out.append(make_event(SOURCE_NAME, ts, detail, project, anchors=anchors))
    return out


def collect_vscode_chat_sessions(
    profiles,
    dt_from,
    dt_to,
    home,
    local_tz,
    classify_project,
    make_event,
) -> List[dict]:
    """Collect VS Code / Copilot chat requests from workspaceStorage chatSessions."""
    results: List[dict] = []
    for base in _base_dirs(Path(home)):
        storage = base / "User" / "workspaceStorage"
        if not storage.is_dir():
            continue
        workspace_map = load_fork_workspaces(base)
        try:
            ws_dirs: Iterable[Path] = storage.iterdir()
        except OSError:
            continue
        for ws_dir in ws_dirs:
            if not ws_dir.is_dir():
                continue
            folder = workspace_map.get(ws_dir.name) or _folder_from_workspace_json(ws_dir)
            if not folder:
                continue
            chat_dir = ws_dir / "chatSessions"
            if not chat_dir.is_dir():
                continue
            try:
                jsonl_files = list(chat_dir.glob("*.jsonl"))
            except OSError:
                continue
            for jsonl in jsonl_files:
                results.extend(
                    _events_from_chat_jsonl(
                        jsonl,
                        folder=folder,
                        profiles=profiles,
                        dt_from=dt_from,
                        dt_to=dt_to,
                        local_tz=local_tz,
                        classify_project=classify_project,
                        make_event=make_event,
                    )
                )
    return results
