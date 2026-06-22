"""Durable append-only JSONL evidence store (opt-in shadow log).

Slice 2 / item 3 of ``docs/specs/local-evidence-shadow-log.md``. Captures
observed evidence into ``~/.gittan/evidence/events/YYYY-MM.jsonl`` so it survives
upstream source-log rotation, cache resets, and vendor retention limits.

Properties:

- **Opt-in only** — nothing is written unless the caller enables it.
- **Append-only**, one ``EvidenceRecord`` JSON per line.
- **Idempotent** — dedup on fingerprint across already-stored records, so
  re-running a report never double-writes.
- **Tamper-evident** — per-month hash chain (each record's ``prev_hash`` equals
  the previous record's ``content_hash``).
- **No background daemon** — capture runs only when a report/status command does.

The JSONL engine was chosen by the measured volume spike (GH-151): real volume
is ~30 records/day, so a swap to SQLite/DuckDB is unnecessary and, thanks to the
engine-agnostic record contract, would be migration-free if ever needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.evidence_record import compute_content_hash, evidence_record_from_event

_LOGGER = logging.getLogger(__name__)


def evidence_base_dir(home: Optional[Path] = None) -> Path:
    """Durable store root: ``~/.gittan/evidence`` (local, never uploaded)."""
    return (home or Path.home()) / ".gittan" / "evidence"


def events_dir(base_dir: Path) -> Path:
    return base_dir / "events"


def _month_key(observed_at_iso: str) -> str:
    # observed_at is a normalized UTC ISO string; first 7 chars are YYYY-MM.
    return (observed_at_iso or "")[:7] or "unknown"


def _month_path(events_directory: Path, month: str) -> Path:
    return events_directory / f"{month}.jsonl"


def load_store_state(events_directory: Path) -> Tuple[set, Dict[str, str]]:
    """Return ``(known_fingerprints, last_content_hash_by_month)``.

    Used for idempotent dedup and to continue each month's hash chain. Missing
    store or unreadable/garbled lines degrade gracefully (skipped, never raise).
    """
    fingerprints: set = set()
    last_hash: Dict[str, str] = {}
    if not events_directory.is_dir():
        return fingerprints, last_hash
    for path in sorted(events_directory.glob("*.jsonl")):
        last: Optional[str] = None
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    fp = rec.get("fingerprint")
                    if fp:
                        fingerprints.add(fp)
                    if rec.get("content_hash"):
                        last = rec["content_hash"]
        except OSError:
            continue
        if last is not None:
            last_hash[path.stem] = last
    return fingerprints, last_hash


def capture_events(
    events: Iterable[Dict[str, Any]],
    *,
    base_dir: Optional[Path] = None,
    home: Optional[Path] = None,
    captured_at: Optional[Any] = None,
) -> Dict[str, Any]:
    """Append new (by fingerprint) events to the monthly JSONL store.

    Idempotent and append-only. The store directory is created only when there
    is something new to write, so a no-op run leaves the filesystem untouched.
    """
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    ev_dir = events_dir(base)
    captured = captured_at if captured_at is not None else datetime.now(timezone.utc)

    fingerprints, last_hash = load_store_state(ev_dir)

    # Build records, then order by observed time so the hash chain is
    # deterministic regardless of collector iteration order.
    records = [evidence_record_from_event(ev, captured_at=captured) for ev in events]
    records.sort(key=lambda r: (r.get("observed_at", ""), r.get("fingerprint", "")))

    appended = 0
    skipped = 0
    seen_this_run: set = set()
    by_month_lines: Dict[str, List[str]] = {}
    for rec in records:
        fp = rec.get("fingerprint")
        if not fp or fp in fingerprints or fp in seen_this_run:
            skipped += 1
            continue
        month = _month_key(rec.get("observed_at", ""))
        # content_hash excludes prev_hash, so chaining it in after the fact keeps
        # both the fingerprint and content_hash stable and valid.
        rec["prev_hash"] = last_hash.get(month)
        last_hash[month] = rec["content_hash"]
        seen_this_run.add(fp)
        by_month_lines.setdefault(month, []).append(
            json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        )
        appended += 1

    if appended:
        ev_dir.mkdir(parents=True, exist_ok=True)
        for month, lines in by_month_lines.items():
            with _month_path(ev_dir, month).open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")

    return {
        "enabled": True,
        "base_dir": str(base),
        "appended": appended,
        "skipped": skipped,
        "months": sorted(by_month_lines.keys()),
    }


def capture_if_enabled(
    shadow_log: Any,
    events: Iterable[Dict[str, Any]],
    *,
    home: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Capture only when ``shadow_log`` is "on"; never raises into the report."""
    if str(shadow_log or "off").strip().lower() != "on":
        return None
    try:
        return capture_events(events, home=home)
    except Exception as exc:  # capture must never break the report
        _LOGGER.warning("Shadow log capture failed: %s", exc)
        return {"enabled": True, "error": str(exc)}


def read_records(events_directory: Path) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield ``(month, record)`` for all stored records, in file + line order."""
    if not events_directory.is_dir():
        return
    for path in sorted(events_directory.glob("*.jsonl")):
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield path.stem, json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def _chain_breaks(by_month: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Return human-readable descriptions of any hash-chain integrity failures."""
    breaks: List[str] = []
    for month in sorted(by_month):
        prev: Optional[str] = None
        for idx, rec in enumerate(by_month[month]):
            if rec.get("prev_hash") != prev:
                breaks.append(f"{month}[{idx}]: prev_hash does not match previous record")
            if rec.get("content_hash") != compute_content_hash(rec):
                breaks.append(f"{month}[{idx}]: content_hash mismatch (record altered)")
            prev = rec.get("content_hash")
    return breaks


def store_health(
    *,
    home: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Read-only health snapshot of the durable evidence store.

    Reports enabled state, totals, today's captures, last capture time, retention
    span, per-source counts, and tamper-evident chain integrity. Never writes.
    """
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    ev_dir = events_dir(base)
    if not ev_dir.is_dir():
        return {"enabled": False, "base_dir": str(base)}

    today_str = today or datetime.now(timezone.utc).date().isoformat()
    by_month: Dict[str, List[Dict[str, Any]]] = {}
    per_source: Dict[str, int] = {}
    total = 0
    captured_today = 0
    last_captured: Optional[str] = None
    for month, rec in read_records(ev_dir):
        by_month.setdefault(month, []).append(rec)
        per_source[rec.get("source", "")] = per_source.get(rec.get("source", ""), 0) + 1
        total += 1
        cap = str(rec.get("captured_at", "") or "")
        if cap and (last_captured is None or cap > last_captured):
            last_captured = cap
        if cap[:10] == today_str:
            captured_today += 1

    breaks = _chain_breaks(by_month)
    months = sorted(by_month)
    return {
        "enabled": True,
        "base_dir": str(base),
        "total_records": total,
        "records_captured_today": captured_today,
        "last_captured_at": last_captured,
        "months": months,
        "retention_span": f"{months[0]}..{months[-1]}" if months else None,
        "per_source": dict(sorted(per_source.items())),
        "chain_ok": not breaks,
        "chain_breaks": breaks,
    }
