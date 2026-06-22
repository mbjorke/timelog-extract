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

from core.evidence_record import evidence_record_from_event

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
