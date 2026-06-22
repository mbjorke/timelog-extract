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
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.evidence_record import (
    compute_content_hash,
    compute_evidence_fingerprint,
    evidence_record_from_event,
)

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


def _read_month_records(path: Path) -> Optional[List[Dict[str, Any]]]:
    """Parse one monthly JSONL file; garbled lines are skipped.

    Returns ``None`` when the file cannot be read (prune must not delete it).
    """
    records: List[Dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return records


def read_records(events_directory: Path) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield ``(month, record)`` for all stored records, in file + line order."""
    if not events_directory.is_dir():
        return
    for path in sorted(events_directory.glob("*.jsonl")):
        records = _read_month_records(path)
        if records is None:
            continue
        for rec in records:
            yield path.stem, rec


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


def replay_into_events(
    live_events: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    *,
    home: Optional[Path] = None,
    base_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Merge stored evidence into ``live_events`` for the window ``[dt_from, dt_to]``.

    Stored records whose fingerprint is not already present live are converted
    back to event dicts (marked ``replayed``) and appended — restoring evidence
    whose upstream source has since rotated. Returns ``(events, restored_count)``.
    """
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    ev_dir = events_dir(base)
    if not ev_dir.is_dir():
        return list(live_events), 0

    live_fps = {
        compute_evidence_fingerprint(ev.get("source"), ev.get("timestamp"), ev.get("detail"))
        for ev in live_events
    }
    window_from = dt_from.astimezone(timezone.utc)
    window_to = dt_to.astimezone(timezone.utc)
    restored: List[Dict[str, Any]] = []
    for _month, rec in read_records(ev_dir):
        fp = rec.get("fingerprint")
        if not fp or fp in live_fps:
            continue
        try:
            obs_dt = datetime.fromisoformat(str(rec.get("observed_at")))
        except (TypeError, ValueError):
            continue
        if obs_dt.tzinfo is None:
            obs_dt = obs_dt.replace(tzinfo=timezone.utc)
        if not (window_from <= obs_dt <= window_to):
            continue
        live_fps.add(fp)
        restored.append(
            {
                "source": rec.get("source", ""),
                "timestamp": obs_dt,
                "detail": rec.get("detail", ""),
                "project": rec.get("project_at_capture", ""),
                "replayed": True,
            }
        )
    return list(live_events) + restored, len(restored)


def maybe_replay(
    live_events: List[Dict[str, Any]],
    *,
    args: Any,
    dt_from: datetime,
    dt_to: datetime,
    home: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    local_tz: Any = None,
) -> List[Dict[str, Any]]:
    """Opt-in replay for CLOSED windows; records the restored count on ``args``.

    Open windows (those including today) return live events unchanged — live
    sources are authoritative there. Never raises into the report.
    """
    setattr(args, "shadow_replay_restored", 0)
    if str(getattr(args, "shadow_replay", "off") or "off").strip().lower() != "on":
        return live_events
    tz = local_tz or timezone.utc
    if dt_to.astimezone(tz).date() >= datetime.now(tz).date():
        return live_events  # open window: do not replay
    try:
        events, restored = replay_into_events(live_events, dt_from, dt_to, home=home, base_dir=base_dir)
        setattr(args, "shadow_replay_restored", restored)
        return events
    except Exception as exc:  # replay must never break the report
        _LOGGER.warning("Shadow log replay failed: %s", exc)
        return live_events


def export_store(
    dest: Any, *, home: Optional[Path] = None, base_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Write all stored records to a single JSONL file (user data export)."""
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    records = [rec for _month, rec in read_records(events_dir(base))]
    dest_path = Path(dest).expanduser()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records)
    dest_path.write_text(body + ("\n" if records else ""), encoding="utf-8")
    return {"records": len(records), "path": str(dest_path)}


def erase_store(*, home: Optional[Path] = None, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Delete the entire local evidence store (user-owned data erase)."""
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    existed = base.exists()
    if existed:
        shutil.rmtree(base)
    removed = existed and not base.exists()
    return {"removed": removed, "path": str(base)}


def prune_older_than(
    days: int,
    *,
    home: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Drop records older than ``days`` and re-link each month's hash chain.

    Retention/privacy control (not a storage need at observed volumes). Records
    with an unparseable ``observed_at`` are kept. Emptied month files are removed.
    """
    if days <= 0:
        raise ValueError("days must be positive")
    base = base_dir if base_dir is not None else evidence_base_dir(home)
    ev_dir = events_dir(base)
    if not ev_dir.is_dir():
        return {"enabled": False, "removed": 0, "kept": 0}
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    removed = 0
    kept = 0
    for path in sorted(ev_dir.glob("*.jsonl")):
        records = _read_month_records(path)
        if records is None:
            continue
        survivors: List[Dict[str, Any]] = []
        for rec in records:
            try:
                obs = datetime.fromisoformat(str(rec.get("observed_at")))
            except (TypeError, ValueError):
                survivors.append(rec)
                continue
            if obs.tzinfo is None:
                obs = obs.replace(tzinfo=timezone.utc)
            if obs < cutoff:
                removed += 1
            else:
                survivors.append(rec)
        kept += len(survivors)
        if not survivors:
            path.unlink()
        elif len(survivors) != len(records):
            prev: Optional[str] = None
            for rec in survivors:
                rec["prev_hash"] = prev
                prev = rec.get("content_hash")
            path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in survivors) + "\n",
                encoding="utf-8",
            )
    return {"enabled": True, "removed": removed, "kept": kept}
