"""Local cache of observed (pre-approval) hours per project+day.

Written as a cheap byproduct of report runs so the agent statusline can compute
``unreported = observed − handled`` without running collectors (Part A of
``docs/task-prompts/gittan-statusline-task.md``).

Mirrors ``core/reported_time.py``: monthly JSONL under
``~/.gittan/observed/YYYY-MM.jsonl``. Each report run merges the months it covers
**keep-max** per ``(project, day)`` — a run can only raise or hold a value, never
lower it, so evidence decay on closed months cannot degrade the record. Observed
hours are computed
with the **same** aggregation the reported layer uses
(``core/reported_sync.py::build_reported_proposals``), so ``observed − handled``
is apples-to-apples against ``core/reported_time.py``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from core.report_service import ReportPayload

_LOGGER = logging.getLogger(__name__)


def observed_base_dir(home: Optional[Path] = None) -> Path:
    """Store root: ``~/.gittan/observed`` (local, never uploaded)."""
    return (home or Path.home()) / ".gittan" / "observed"


def _month_path(base_dir: Path, month: str) -> Path:
    return base_dir / f"{month}.jsonl"


def _coerce_row(data: object) -> Optional[dict]:
    """Normalize a parsed cache record, or return None if it is malformed.

    Guards the keep-max merge against valid-JSON-but-wrong-shape lines (e.g. a list,
    or a non-numeric ``hours``): only records with non-empty string ``project`` /
    ``date`` and a numeric ``hours`` are kept; everything else is skipped.
    """
    if not isinstance(data, dict):
        return None
    project_raw = data.get("project")
    date_raw = data.get("date")
    if not isinstance(project_raw, str) or not isinstance(date_raw, str):
        return None
    project = project_raw.strip()
    date = date_raw.strip()
    if not project or not date or "hours" not in data:
        return None
    try:
        hours = float(data["hours"])
    except (TypeError, ValueError):
        return None
    return {"project": project, "date": date, "hours": hours, "captured_at": data.get("captured_at", "")}


def write_observed_summary(report: "ReportPayload", home: Optional[Path] = None) -> int:
    """Persist per-``(project, day)`` observed hours from a report.

    Returns the number of rows written. Merge is **keep-max** per ``(project, date)``:
    a run can only raise or hold a stored observed value, never lower it, so evidence
    decay on closed months cannot silently degrade the record (see
    ``docs/incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md``).
    """
    from core.reported_sync import build_reported_proposals

    proposals = build_reported_proposals(report)  # one per (project, day)
    if not proposals:
        return 0
    totals: Dict[Tuple[str, str], float] = {}
    for proposal in proposals:
        key = (proposal.project, proposal.date)
        totals[key] = totals.get(key, 0.0) + float(proposal.hours)

    base = observed_base_dir(home)
    base.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0
    by_month: Dict[str, list] = {}
    for (project, day), hours in totals.items():
        row = {"project": project, "date": day, "hours": round(hours, 2), "captured_at": captured_at}
        by_month.setdefault(day[:7] or "unknown", []).append(row)
    for month, rows in by_month.items():
        month_file = _month_path(base, month)
        # Keep rows from other months verbatim; merge THIS month keep-max per
        # (project, date) so a report run can only raise or hold an observed value,
        # never lower it. Evidence for closed months decays as sources rotate, and a
        # plain overwrite would silently degrade the record on every rerun.
        existing_other_months = []
        merged: Dict[Tuple[str, str], dict] = {}
        if month_file.exists():
            try:
                with month_file.open(encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue  # skip garbled JSON
                        existing = _coerce_row(data)
                        if existing is None:
                            continue  # valid JSON but not a well-formed observed row
                        if existing["date"][:7] != month:
                            existing_other_months.append(line)  # keep verbatim
                            continue
                        key = (existing["project"], existing["date"])
                        prev = merged.get(key)
                        if prev is None or existing["hours"] > prev["hours"]:
                            merged[key] = existing
            except OSError as exc:
                # Fail closed: if the existing month can't be fully read, do NOT
                # rewrite it — an empty/partial merge would wipe good rows (the very
                # data-loss this cache is meant to prevent). Skip; retry next run.
                _LOGGER.warning("observed cache: skipping %s, read failed: %s", month, exc)
                continue
        for row in rows:
            key = (row["project"], row["date"])
            prev = merged.get(key)
            if prev is None or float(row["hours"]) > prev["hours"]:
                merged[key] = row
        # Write full payload to a temp file, then swap into place atomically.
        fd, temp_path = tempfile.mkstemp(
            dir=month_file.parent, prefix=".tmp_", suffix=".jsonl"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for line in existing_other_months:
                    fh.write(line + "\n")
                for row in sorted(merged.values(), key=lambda r: (r["date"], r["project"])):
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    written += 1
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, month_file)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    return written


def observed_hours_by_project_day(home: Optional[Path] = None) -> Dict[Tuple[str, str], float]:
    """Observed hours per ``(project, day)`` from the cache (empty if none).

    Values are a keep-max high-water mark across report runs; garbled lines are
    skipped, never raised."""
    base = observed_base_dir(home)
    if not base.is_dir():
        return {}
    latest: Dict[Tuple[str, str], float] = {}
    for path in sorted(base.glob("*.jsonl")):
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        _LOGGER.warning("Skipping unreadable observed line in %s", path.name)
                        continue
                    row = _coerce_row(data)
                    if row is not None:
                        latest[(row["project"], row["date"])] = row["hours"]
        except OSError as exc:
            _LOGGER.warning("Could not read observed file %s: %s", path, exc)
    return latest


def observed_last_capture_date(home: Optional[Path] = None) -> Optional[str]:
    """The most recent ``captured_at`` date (``YYYY-MM-DD``) in the cache, or None.

    Lets the statusline distinguish "all reported" from "the cache wasn't refreshed
    today" (i.e. ``gittan report`` hasn't run) so it never claims all-clear on stale
    data."""
    base = observed_base_dir(home)
    if not base.is_dir():
        return None
    latest: Optional[datetime] = None
    for path in sorted(base.glob("*.jsonl")):
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        captured = datetime.fromisoformat(str(json.loads(line).get("captured_at", "")))
                        if captured.tzinfo is None:  # legacy/hand-edited rows: treat as UTC
                            captured = captured.replace(tzinfo=timezone.utc)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        continue
                    if latest is None or captured > latest:
                        latest = captured
        except OSError as exc:
            _LOGGER.warning("Could not read observed file %s: %s", path, exc)
    # Compare in local time: captured_at is UTC but the statusline's "today" is local.
    return latest.astimezone().date().isoformat() if latest is not None else None
