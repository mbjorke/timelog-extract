"""Bind a session to a project by decision, not by pattern.

A chat has no repo, no working directory, no URL worth matching. Today the only
way to attribute one is to add a ``match_term`` — but a term is not an answer
about *this* conversation, it is a rule that matches every future event
containing that text. One throwaway decision becomes permanent classification
noise. That is the patching this module removes.

An **intent record** binds one key to one project:

    {"schema_version": 1, "captured_at": "…", "key_kind": "session",
     "key": "abc123", "project": "Customer X", "via": "review", "note": ""}

Append-only JSONL at ``~/.gittan/intent-capture.jsonl`` (the location and record
shape follow ``docs/specs/intent-capture.md``). The log is never rewritten: a
re-decision appends, and the latest record for a key wins, so the history of what
you decided when stays readable.

Two rules, both confirmed by the maintainer on 2026-07-26:

**An intent beats a match_term.** A deliberate human answer outranks a heuristic
pattern — otherwise the question is pointless, since a stale rule could silently
override the answer. Overridden events carry
``anchors.project_from = "intent"`` so a report can always say *why* a row
belongs where it does.

**A session belongs to one project.** Binding part of a session to a different
project is out of scope, not unfinished — so a single key per session is the whole
model, and code may rely on that.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

INTENT_SCHEMA_VERSION = 1

#: Anchor kinds an intent record may bind. ``session`` is the one that exists
#: today; ``url`` is reserved for the browser-chat case in intent-capture.md.
SUPPORTED_KEY_KINDS = ("session", "url")


def intent_path(home: Optional[Path] = None) -> Path:
    """Append-only intent log inside the operator's own data dir."""
    return (home or Path.home()) / ".gittan" / "intent-capture.jsonl"


def normalize_key(value: Any) -> str:
    """Case-fold a binding key.

    ``make_event`` lowercases every anchor value except ``label``
    (``core/events.py::_normalize_anchor_value``), so a session anchor reaching a
    report is already lower case. Normalizing here too means a key copied from
    anywhere — Claude Desktop's "Copy link", a log line, this command's own
    output — binds the same session instead of silently matching nothing.
    """
    return str(value or "").strip().lower()


def _normalize_stamp(value: Any) -> str:
    if isinstance(value, datetime):
        stamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc).isoformat()
    return str(value)


def record_intent(
    key: str,
    project: str,
    *,
    key_kind: str = "session",
    via: str = "cli",
    note: str = "",
    home: Optional[Path] = None,
    path: Optional[Path] = None,
    captured_at: Optional[Any] = None,
) -> Dict[str, Any]:
    """Append one binding. Returns the record written."""
    clean_key = normalize_key(key)
    clean_project = str(project or "").strip()
    if not clean_key:
        raise ValueError("intent needs a key (the session id)")
    if not clean_project:
        raise ValueError("intent needs a project name")
    if key_kind not in SUPPORTED_KEY_KINDS:
        raise ValueError(
            f"unsupported key_kind {key_kind!r} (known: {', '.join(SUPPORTED_KEY_KINDS)})"
        )

    record = {
        "schema_version": INTENT_SCHEMA_VERSION,
        "captured_at": _normalize_stamp(captured_at or datetime.now(timezone.utc)),
        "key_kind": key_kind,
        "key": clean_key,
        "project": clean_project,
        "via": str(via or "cli"),
        "note": str(note or ""),
    }
    target = Path(path) if path is not None else intent_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def read_intents(
    *, home: Optional[Path] = None, path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Read every record in log order. Unreadable lines are skipped, not fatal."""
    target = Path(path) if path is not None else intent_path(home)
    if not target.is_file():
        return []
    records: List[Dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("key") and record.get("project"):
            records.append(record)
    return records


def resolve_intents(
    *, home: Optional[Path] = None, path: Optional[Path] = None
) -> Dict[tuple, Dict[str, Any]]:
    """Collapse the log to the current binding per ``(key_kind, key)``.

    Later records win, so re-deciding is an append rather than an edit.
    """
    current: Dict[tuple, Dict[str, Any]] = {}
    for record in read_intents(home=home, path=path):
        key = (str(record.get("key_kind") or "session"), normalize_key(record["key"]))
        current[key] = record
    return current


def apply_intents(
    events: Sequence[Dict[str, Any]],
    *,
    home: Optional[Path] = None,
    path: Optional[Path] = None,
    intents: Optional[Dict[tuple, Dict[str, Any]]] = None,
) -> tuple[List[Dict[str, Any]], int]:
    """Re-project events whose session was bound by a decision.

    Returns ``(events, changed_count)``. Events are copied, never mutated in
    place, and a re-projected event records where its project came from.
    """
    bindings = intents if intents is not None else resolve_intents(home=home, path=path)
    if not bindings:
        return list(events), 0

    out: List[Dict[str, Any]] = []
    changed = 0
    for event in events:
        anchors = event.get("anchors") or {}
        session = normalize_key(anchors.get("session")) if isinstance(anchors, dict) else ""
        binding = bindings.get(("session", session)) if session else None
        if not binding or binding["project"] == event.get("project"):
            out.append(event)
            continue
        updated = dict(event)
        updated["project"] = binding["project"]
        updated["anchors"] = {
            **anchors,
            "project_from": "intent",
            "project_before_intent": event.get("project", ""),
        }
        out.append(updated)
        changed += 1
    return out, changed


def unbound_sessions(
    events: Iterable[Dict[str, Any]],
    *,
    uncategorized: str = "Uncategorized",
    home: Optional[Path] = None,
    path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Sessions that carry hours but no project — the queue worth asking about.

    One row per session, newest first, with the label and turn count that make
    the question answerable ("which customer was *this*?").
    """
    bindings = resolve_intents(home=home, path=path)
    rows: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if str(event.get("project") or "") != uncategorized:
            continue
        anchors = event.get("anchors") or {}
        if not isinstance(anchors, dict):
            continue
        session = normalize_key(anchors.get("session"))
        if not session or ("session", session) in bindings:
            continue
        stamp = event.get("timestamp")
        row = rows.setdefault(
            session,
            {
                "session": session,
                "source": event.get("source", ""),
                "label": str(anchors.get("label") or ""),
                "events": 0,
                "first_seen": stamp,
                "last_seen": stamp,
            },
        )
        row["events"] += 1
        if stamp is not None:
            if row["first_seen"] is None or stamp < row["first_seen"]:
                row["first_seen"] = stamp
            if row["last_seen"] is None or stamp > row["last_seen"]:
                row["last_seen"] = stamp
        if not row["label"] and anchors.get("label"):
            row["label"] = str(anchors["label"])
    return sorted(rows.values(), key=lambda r: (str(r["last_seen"]), r["session"]), reverse=True)
