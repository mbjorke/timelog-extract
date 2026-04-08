from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def load_cursor_workspaces(home: Path):
    storage_dir = home / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    workspace_map = {}
    if not storage_dir.exists():
        return workspace_map
    for workspace_json in storage_dir.glob("*/workspace.json"):
        workspace_id = workspace_json.parent.name
        try:
            data = json.loads(workspace_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_uri = data.get("folder") or data.get("workspace")
        if not raw_uri:
            continue
        parsed = urlparse(raw_uri)
        path = unquote(parsed.path) if parsed.scheme == "file" else raw_uri
        workspace_map[workspace_id] = path
    return workspace_map


def collect_cursor(profiles, dt_from, dt_to, home, local_tz, classify_project, make_event):
    workspace_map = load_cursor_workspaces(home)
    logs_dir = home / "Library" / "Application Support" / "Cursor" / "logs"
    if not logs_dir.exists():
        return []

    results = []
    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    ts_iso_bracket_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?\]")
    workspace_id_pattern = re.compile(r"workspaceStorage/([0-9a-f]{32})|old id ([0-9a-f]{32})-")
    workspace_path_pattern = re.compile(r"(/Users/[^\"'\s]+)")

    def _parse_cursor_log_ts(line: str):
        m = ts_pattern.match(line)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=local_tz)
            except ValueError:
                return None
        m = ts_iso_bracket_pattern.match(line)
        if m:
            iso = (m.group(1) + (m.group(2) or "")).replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(iso)
            except ValueError:
                return None
        return None

    for log_file in logs_dir.glob("**/*.log"):
        try:
            with open(log_file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    ts = _parse_cursor_log_ts(line)
                    if not ts or not (dt_from <= ts <= dt_to):
                        continue
                    workspace_path = None
                    m_id = workspace_id_pattern.search(line)
                    if m_id and workspace_map:
                        workspace_id = m_id.group(1) or m_id.group(2)
                        workspace_path = workspace_map.get(workspace_id)
                    if not workspace_path:
                        m_path = workspace_path_pattern.search(line)
                        if m_path:
                            workspace_path = m_path.group(1)
                    if not workspace_path:
                        continue
                    project = classify_project(f"{workspace_path} {line}", profiles)
                    detail = f"{Path(workspace_path).name} — {line.strip()[:90]}"
                    results.append(make_event("Cursor", ts, detail, project))
        except OSError:
            continue
    return results


def collect_cursor_checkpoints(
    profiles,
    dt_from,
    dt_to,
    checkpoints_dir: Path,
    home: Path,
    classify_project,
    make_event,
    source_name: str,
):
    if not checkpoints_dir.is_dir():
        return []
    workspace_map = load_cursor_workspaces(home)
    results = []
    for meta_path in checkpoints_dir.glob("*/metadata.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ms = data.get("startTrackingDateUnixMilliseconds")
        if ms is None:
            continue
        try:
            ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        paths = []
        for rf in data.get("requestFiles") or []:
            p = rf.get("fsPath")
            if p:
                paths.append(str(p))
        wid = data.get("workspaceId")
        if wid:
            mapped = workspace_map.get(wid)
            if mapped:
                paths.append(str(mapped))
        hay = " ".join(paths)
        if not hay:
            continue
        project = classify_project(hay, profiles)
        agent_id = str(data.get("agentRequestId", "")).split("-")[0][:8]
        label = Path(paths[0]).name if paths else "checkpoint"
        detail = f"checkpoint {agent_id}… — {label}"
        results.append(make_event(source_name, ts, detail, project))
    return results
