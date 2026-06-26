"""Local store for ``reported_time`` — the confirmed/edited layer between
observed/classified time and approved invoice time.

See ``docs/specs/scheduled-reported-time-bridge.md``. Records are one JSON per
line in ``~/.gittan/reported/YYYY-MM.jsonl`` (monthly, global), mirroring
``core/evidence_store.py``. The store is append-only and event-sourced: re-writing
the same logical unit (same ``id``) appends a new line and the **latest write
wins**, so a unit can move ``proposed -> confirmed -> edited`` over time.

Layer rules (from the evidence policy + invoice reality):

- Only ``confirmed`` / ``edited`` records are pushable/billable; ``proposed`` are
  shown but not counted; ``dismissed`` are excluded.
- Non-manual records must carry ``origin_ref`` (provenance back to real evidence).
- ``manual`` records hold net-new time gittan never observed (SFTP, mail,
  meetings); they have no ``origin_ref`` but require a ``note`` so they are never
  a silent fabrication.

Phase 1 (this module) is storage + query only — no CLI, no sync wiring.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {"proposed", "confirmed", "edited", "dismissed"}
VALID_SOURCES = {"calendar", "toggl", "session", "manual"}
# States that count as reported (pushable / billable).
REPORTED_STATES = {"confirmed", "edited"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reported_base_dir(home: Optional[Path] = None) -> Path:
    """Store root: ``~/.gittan/reported`` (local, never uploaded)."""
    return (home or Path.home()) / ".gittan" / "reported"


def _month_path(base_dir: Path, month: str) -> Path:
    return base_dir / f"{month}.jsonl"


def compute_reported_id(
    date: str,
    project: str,
    source: str,
    origin_ref: List[str],
    note: str,
    issue_key: Optional[str] = None,
) -> str:
    """Deterministic id for a reported unit so re-writes are idempotent.

    Non-manual units key on (date, project, source, origin); manual units key on
    (date, project, note) since they have no origin. When an ``issue_key`` is set
    (Phase 3b) the basis is an unambiguous JSON array so two issues on one
    project+day are distinct (and free-text notes can't collide with an appended
    key); records without an ``issue_key`` keep the pre-3b string basis, so
    existing ids are unchanged.
    """
    normalized_issue_key = str(issue_key).strip() if issue_key else ""
    if normalized_issue_key:
        payload = note.strip() if source == "manual" else sorted(origin_ref)
        basis = json.dumps(
            [date, project, source, payload, normalized_issue_key],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    elif source == "manual":
        basis = f"{date}|{project}|manual|{note.strip()}"
    else:
        basis = f"{date}|{project}|{source}|{','.join(sorted(origin_ref))}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


@dataclass
class ReportedTimeRecord:
    date: str  # local YYYY-MM-DD the time is reported against
    project: str
    hours: float
    source: str  # calendar | toggl | session | manual
    state: str  # proposed | confirmed | edited | dismissed
    origin_ref: List[str] = field(default_factory=list)
    note: str = ""
    edited_from_hours: Optional[float] = None
    captured_at: str = ""
    confirmed_at: Optional[str] = None
    issue_key: Optional[str] = None  # Phase 3b: the Jira issue this time posts to
    id: str = ""

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"invalid reported_time state '{self.state}'")
        if self.source not in VALID_SOURCES:
            raise ValueError(f"invalid reported_time source '{self.source}'")
        if self.date is None or not str(self.date):
            raise ValueError("reported_time requires a date")
        if self.project is None or not str(self.project):
            raise ValueError("reported_time requires a project")
        if self.source == "manual":
            if not str(self.note).strip():
                raise ValueError("manual reported_time requires a note (no silent net-new time)")
            if self.origin_ref:
                raise ValueError("manual reported_time must not have origin_ref (manual has no origin)")
        elif not self.origin_ref:
            raise ValueError(f"{self.source} reported_time requires origin_ref (provenance)")
        if not self.captured_at:
            self.captured_at = _utc_now_iso()
        if self.confirmed_at is None and self.state in REPORTED_STATES:
            self.confirmed_at = _utc_now_iso()
        if self.issue_key is not None:
            self.issue_key = str(self.issue_key).strip() or None
        if not self.id:
            self.id = compute_reported_id(
                self.date, self.project, self.source, list(self.origin_ref),
                self.note, self.issue_key,
            )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def record_from_dict(data: dict) -> ReportedTimeRecord:
    """Rebuild a record from a stored dict; keeps the stored id/timestamps."""
    return ReportedTimeRecord(
        date=str(data.get("date", "")),
        project=str(data.get("project", "")),
        hours=float(data.get("hours", 0.0)),
        source=str(data.get("source", "")),
        state=str(data.get("state", "")),
        origin_ref=list(data.get("origin_ref") or []),
        note=str(data.get("note", "")),
        edited_from_hours=data.get("edited_from_hours"),
        captured_at=str(data.get("captured_at", "")),
        confirmed_at=data.get("confirmed_at"),
        issue_key=data.get("issue_key"),
        id=str(data.get("id", "")),
    )


def append_record(record: ReportedTimeRecord, home: Optional[Path] = None) -> Path:
    """Append one record to its month file; returns the file path written."""
    base = reported_base_dir(home)
    base.mkdir(parents=True, exist_ok=True)
    month = (record.date or "")[:7] or "unknown"
    path = _month_path(base, month)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")
    return path


def load_records(home: Optional[Path] = None, months: Optional[List[str]] = None) -> List[ReportedTimeRecord]:
    """Load all stored records (optionally only given ``YYYY-MM`` months), in
    write order. Garbled/unreadable lines are skipped, never raised."""
    base = reported_base_dir(home)
    if not base.is_dir():
        return []
    if months is not None:
        paths = [_month_path(base, m) for m in months]
    else:
        paths = sorted(base.glob("*.jsonl"))
    out: List[ReportedTimeRecord] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(record_from_dict(json.loads(line)))
                    except (json.JSONDecodeError, ValueError):
                        _LOGGER.warning("Skipping unreadable reported_time line in %s", path.name)
        except OSError as exc:
            _LOGGER.warning("Could not read reported_time file %s: %s", path, exc)
    return out


def latest_by_id(records: List[ReportedTimeRecord]) -> Dict[str, ReportedTimeRecord]:
    """Collapse the append-only log: the last write for each id wins."""
    latest: Dict[str, ReportedTimeRecord] = {}
    for rec in records:
        latest[rec.id] = rec
    return latest


def query(
    home: Optional[Path] = None,
    *,
    project: Optional[str] = None,
    date: Optional[str] = None,
    states: Optional[set] = None,
) -> List[ReportedTimeRecord]:
    """Return the current (latest-per-id) records, optionally filtered."""
    records = list(latest_by_id(load_records(home)).values())
    result = []
    for rec in records:
        if project is not None and rec.project != project:
            continue
        if date is not None and rec.date != date:
            continue
        if states is not None and rec.state not in states:
            continue
        result.append(rec)
    return result


def reported_hours_by_project_day(
    home: Optional[Path] = None,
    states: Optional[set] = None,
) -> Dict[Tuple[str, str], float]:
    """Project+day granularity at the read layer: sum reported (confirmed/edited)
    hours per ``(project, date)``. This is what sync/invoice consume."""
    if states is None:
        states = REPORTED_STATES
    totals: Dict[Tuple[str, str], float] = {}
    for rec in latest_by_id(load_records(home)).values():
        if rec.state not in states:
            continue
        key = (rec.project, rec.date)
        totals[key] = totals.get(key, 0.0) + float(rec.hours)
    return totals
