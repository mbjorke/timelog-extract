"""Local, append-only operation log for Toggl pushes + rollback support.

The solo-first model (`docs/ideas/simple-invoicing-model.md`) requires a local
record of every push so a regretted `gittan toggl-sync` can be undone. One
``toggl-sync`` run is one **operation** (``op_id``); each posted time entry is
one JSONL row sharing that ``op_id``. ``--rollback <op-id>`` deletes the entries
that op created (Toggl ``DELETE``), idempotently.

The log lives under the Gittan home (``~/.gittan/toggl_oplog.jsonl`` by default,
or ``$GITTAN_HOME``) — never committed, single user-owned file.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import ENV_GITTAN_HOME, canonical_gittan_home

OPLOG_FILENAME = "toggl_oplog.jsonl"


def oplog_path(home: Optional[Path] = None) -> Path:
    """Resolve the op-log file path, honouring ``$GITTAN_HOME`` like the config."""
    if home is not None:
        return home / OPLOG_FILENAME
    env_home = str(os.environ.get(ENV_GITTAN_HOME, "")).strip()
    base = Path(env_home).expanduser() if env_home else canonical_gittan_home()
    return base / OPLOG_FILENAME


def new_op_id() -> str:
    """Short, sortable-ish operation id: ``YYYYmmddThhmmssZ-<hex6>``."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def payload_hash(payload: Dict[str, Any]) -> str:
    """Stable SHA-256 (first 16 hex) of a posted payload, for the audit row."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class OpLogRow:
    op_id: str
    ts: str
    workspace_id: int
    entry_id: str
    project_id: int
    day: str
    marker_tag: str
    payload_hash: str
    rolled_back: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OpLogRow":
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            op_id=str(d.get("op_id", "")),
            ts=str(d.get("ts", "")),
            workspace_id=int(d.get("workspace_id", 0)),
            entry_id=str(d.get("entry_id", "")),
            project_id=int(d.get("project_id", 0)),
            day=str(d.get("day", "")),
            marker_tag=str(d.get("marker_tag", "")),
            payload_hash=str(d.get("payload_hash", "")),
            rolled_back=bool(d.get("rolled_back", False)),
            extra=extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "op_id": self.op_id,
            "ts": self.ts,
            "workspace_id": self.workspace_id,
            "entry_id": self.entry_id,
            "project_id": self.project_id,
            "day": self.day,
            "marker_tag": self.marker_tag,
            "payload_hash": self.payload_hash,
            "rolled_back": self.rolled_back,
        }
        base.update(self.extra)
        return base


def record_push(
    *,
    op_id: str,
    workspace_id: int,
    entry_id: str,
    project_id: int,
    day: str,
    marker_tag: str,
    payload: Dict[str, Any],
    home: Optional[Path] = None,
) -> OpLogRow:
    """Append one row for a just-posted Toggl entry and return it."""
    row = OpLogRow(
        op_id=op_id,
        ts=datetime.now(timezone.utc).isoformat(),
        workspace_id=int(workspace_id),
        entry_id=str(entry_id),
        project_id=int(project_id),
        day=day,
        marker_tag=marker_tag,
        payload_hash=payload_hash(payload),
    )
    path = oplog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row.to_dict(), separators=(",", ":")) + "\n")
    return row


def read_oplog(home: Optional[Path] = None) -> List[OpLogRow]:
    """Read all rows (tolerating blank/corrupt lines) in file order."""
    path = oplog_path(home)
    if not path.is_file():
        return []
    rows: List[OpLogRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(OpLogRow.from_dict(json.loads(line)))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue  # skip a damaged line rather than abort a rollback
    return rows


def rows_for_op(op_id: str, home: Optional[Path] = None) -> List[OpLogRow]:
    return [r for r in read_oplog(home) if r.op_id == op_id]


def list_ops(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Summarise ops newest-first: op_id, entry count, days, rolled-back count."""
    by_op: Dict[str, List[OpLogRow]] = {}
    for row in read_oplog(home):
        by_op.setdefault(row.op_id, []).append(row)
    out: List[Dict[str, Any]] = []
    for op_id, rows in by_op.items():
        out.append(
            {
                "op_id": op_id,
                "ts": rows[0].ts,
                "entries": len(rows),
                "rolled_back": sum(1 for r in rows if r.rolled_back),
                "days": sorted({r.day for r in rows}),
            }
        )
    out.sort(key=lambda o: o["ts"], reverse=True)
    return out


def mark_rolled_back(op_id: str, entry_ids: set, home: Optional[Path] = None) -> None:
    """Rewrite the log, flagging the named entries of ``op_id`` as rolled back.

    A full rewrite (not an append) keeps ``rolled_back`` a single source of truth
    so a re-run rollback is a clean no-op.
    """
    path = oplog_path(home)
    rows = read_oplog(home)
    if not rows:
        return
    for row in rows:
        if row.op_id == op_id and row.entry_id in entry_ids:
            row.rolled_back = True
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row.to_dict(), separators=(",", ":")) + "\n")
        fh.flush()
        os.fsync(fh.fileno())  # durable temp before the atomic replace
    tmp.replace(path)
    # fsync the directory so the rename itself survives a crash/power loss.
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
