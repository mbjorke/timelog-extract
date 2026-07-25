"""Capture AI session evidence from *this device* into the evidence ledger.

Gittan's collectors reconstruct a day from artifacts that happen to survive on
one machine. That premise breaks as soon as work moves: a session run in a cloud
container writes its transcript inside that container, and the container is
reclaimed. The artifact is the shape Gittan already parses — it is simply on a
different device, and a short-lived one.

This module closes that gap without inventing a new evidence kind:

* read the session transcripts this device has (``collect_claude_code`` already
  parses them, and already takes a ``home``),
* tag each event with the **device** that observed it, in the existing
  ``source_provenance`` slot — no schema change, and the fingerprint
  (source + observed_at + detail) is unchanged, so the *same* session captured
  from two devices merges into one record instead of double-counting,
* append through :func:`core.evidence_store.capture_events`, which is
  append-only, hash-chained and idempotent.

A device whose ledger is not the canonical one (a container, a borrowed
machine) can ``export`` ledger-shaped records instead of writing locally; the
canonical device merges them with :func:`import_records`. Both directions carry
the same records, so a merge is idempotent no matter how often it runs.

Deliberately *not* here: nothing reads conversation titles or content into
identity. A captured record carries timestamps, the source name, the detail line
the collector already produced, and the device. Promoting a live chat title to
hours identity stays out of scope (GH-354's do-not-build rule).
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from core import evidence_store
from core.domain import classify_project
from core.events import make_event

UNCATEGORIZED = "Uncategorized"

#: Sources this device can capture, mapped to their collector.
#: Each entry takes ``(profiles, dt_from, dt_to, home, classify, make_event)``.
CAPTURE_SOURCES: Dict[str, str] = {"claude-code": "Claude Code CLI"}


def device_name(explicit: Optional[str] = None) -> str:
    """Return the device label for captured evidence.

    An explicit name wins; otherwise the host name, which is stable enough to
    tell a laptop from a container without identifying a person.
    """
    name = str(explicit or "").strip()
    if not name:
        try:
            name = socket.gethostname().strip()
        except OSError:  # pragma: no cover - hostname lookup is not critical
            name = ""
    return name or "unknown-device"


def _classify(text: str, profiles: Sequence[Dict[str, Any]]) -> str:
    return classify_project(text, list(profiles), UNCATEGORIZED)


def _make_event(
    source: str, ts: Any, detail: str, project: str, anchors: Optional[dict] = None
) -> Dict[str, Any]:
    return make_event(source, ts, detail, project, UNCATEGORIZED, anchors=anchors)


def collect_device_events(
    profiles: Sequence[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    *,
    home: Path,
    device: str,
    sources: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Collect this device's session events, tagged with their device.

    ``sources`` selects keys of :data:`CAPTURE_SOURCES`; the default is all.
    """
    from collectors.ai_logs import collect_claude_code

    collectors: Dict[str, Callable[..., List[Dict[str, Any]]]] = {
        "claude-code": collect_claude_code,
    }
    wanted = list(sources) if sources is not None else list(CAPTURE_SOURCES)
    unknown = [name for name in wanted if name not in collectors]
    if unknown:
        raise ValueError(
            f"unknown capture source(s): {', '.join(sorted(unknown))} "
            f"(known: {', '.join(sorted(collectors))})"
        )

    events: List[Dict[str, Any]] = []
    for name in wanted:
        collected = collectors[name](
            list(profiles), dt_from, dt_to, Path(home), _classify, _make_event
        )
        for event in collected:
            events.append(tag_device(event, device, captured_via=name))
    events.sort(key=lambda e: (str(e.get("timestamp")), str(e.get("detail"))))
    return events


def tag_device(event: Dict[str, Any], device: str, *, captured_via: str) -> Dict[str, Any]:
    """Attach device provenance without disturbing the event's identity."""
    tagged = dict(event)
    provenance = dict(tagged.get("source_provenance") or {})
    provenance.update({"device": device, "captured_via": captured_via})
    tagged["source_provenance"] = provenance
    return tagged


def records_from_events(
    events: Sequence[Dict[str, Any]], *, captured_at: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Build ledger-shaped records for transport to another device.

    ``prev_hash`` is left unset on purpose: the chain belongs to the store that
    finally accepts the records, and is linked there on append.
    """
    from core.evidence_record import evidence_record_from_event

    stamp = captured_at or datetime.now(timezone.utc)
    return [evidence_record_from_event(event, captured_at=stamp) for event in events]


def events_from_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert ledger records back to collector-shaped events for re-append."""
    events: List[Dict[str, Any]] = []
    for record in records:
        events.append(
            {
                "source": record.get("source", ""),
                "timestamp": record.get("observed_at"),
                "detail": record.get("detail", ""),
                "project": record.get("project_at_capture", "") or UNCATEGORIZED,
                "source_provenance": record.get("source_provenance"),
            }
        )
    return events


def write_records_file(records: Sequence[Dict[str, Any]], dest: Any) -> Dict[str, Any]:
    """Write records as JSONL, matching ``gittan evidence --export`` output."""
    path = Path(dest).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records
    )
    path.write_text(body + ("\n" if records else ""), encoding="utf-8")
    return {"records": len(records), "path": str(path)}


def read_records_file(source: Any) -> List[Dict[str, Any]]:
    """Read a JSONL export, skipping blank lines. Raises on malformed JSON."""
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"no such export file: {path}")
    records: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {number} is not valid JSON ({exc.msg})") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}: line {number} is not a JSON object")
        records.append(record)
    return records


def import_records(
    source: Any, *, home: Optional[Path] = None, base_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Merge another device's exported records into this device's ledger."""
    records = read_records_file(source)
    result = evidence_store.capture_events(
        events_from_records(records), home=home, base_dir=base_dir
    )
    result["read"] = len(records)
    result["devices"] = sorted(
        {
            str((record.get("source_provenance") or {}).get("device") or "")
            for record in records
        }
        - {""}
    )
    return result


def capture_device_evidence(
    profiles: Sequence[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    *,
    home: Path,
    device: Optional[str] = None,
    sources: Optional[Iterable[str]] = None,
    export_to: Optional[Any] = None,
    dry_run: bool = False,
    base_dir: Optional[Path] = None,
    store_home: Optional[Path] = None,
    if_enabled: bool = False,
    config_path: Any = None,
) -> Dict[str, Any]:
    """Capture this device's session evidence.

    Writes to the local ledger, or to ``export_to`` when this device's store is
    not the canonical one. ``dry_run`` reports what would happen and writes
    nothing, anywhere.

    ``if_enabled`` makes the run respect the persistent ``shadow_log`` config
    setting and do nothing when it is off. Automation (a timer) should pass it;
    an operator typing ``gittan capture`` should not — running the command *is*
    the consent, and a silent no-op would be baffling.
    """
    if if_enabled and evidence_store.shadow_log_config_setting(config_path) != "on":
        return {
            "device": device_name(device),
            "collected": 0,
            "dry_run": bool(dry_run),
            "projects": [],
            "appended": 0,
            "skipped": 0,
            "destination": None,
            "skipped_reason": "shadow_log is not on",
        }
    resolved_device = device_name(device)
    events = collect_device_events(
        profiles, dt_from, dt_to, home=home, device=resolved_device, sources=sources
    )
    summary: Dict[str, Any] = {
        "device": resolved_device,
        "collected": len(events),
        "dry_run": bool(dry_run),
        "projects": sorted({str(event.get("project") or "") for event in events} - {""}),
    }
    if dry_run:
        summary.update({"appended": 0, "skipped": 0, "destination": None})
        return summary
    if export_to is not None:
        written = write_records_file(records_from_events(events), export_to)
        summary.update(
            {"appended": written["records"], "skipped": 0, "destination": written["path"]}
        )
        return summary
    result = evidence_store.capture_events(
        events, home=store_home if store_home is not None else home, base_dir=base_dir
    )
    summary.update(
        {
            "appended": result.get("appended", 0),
            "skipped": result.get("skipped", 0),
            "destination": result.get("base_dir"),
        }
    )
    return summary
