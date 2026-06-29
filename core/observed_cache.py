"""Local cache of observed (pre-approval) hours per project+day.

Written as a cheap byproduct of report runs so the agent statusline can compute
``unreported = observed − handled`` without running collectors (Part A of
``docs/task-prompts/gittan-statusline-task.md``).

Mirrors ``core/reported_time.py``: monthly JSONL under
``~/.gittan/observed/YYYY-MM.jsonl``. Each report run atomically replaces all
rows for the months it covers (stale entries removed). Observed hours are computed
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


def write_observed_summary(report: "ReportPayload", home: Optional[Path] = None) -> int:
    """Persist per-``(project, day)`` observed hours from a report.

    Returns the number of rows written. Each run is authoritative for the months it
    covers: all rows for those months are replaced atomically (stale entries removed).
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
        # Atomic replacement: read existing rows from other months, discard this month
        existing_other_months = []
        if month_file.exists():
            try:
                with month_file.open(encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            # Keep rows from other months (in case file naming was wrong)
                            if str(data.get("date", ""))[:7] != month:
                                existing_other_months.append(line)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            pass  # skip garbled lines
            except OSError:
                pass  # proceed with empty existing set
        # Write full payload to a temp file, then swap into place atomically.
        fd, temp_path = tempfile.mkstemp(
            dir=month_file.parent, prefix=".tmp_", suffix=".jsonl"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for line in existing_other_months:
                    fh.write(line + "\n")
                for row in sorted(rows, key=lambda r: (r["date"], r["project"])):
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
    """Latest observed hours per ``(project, day)`` from the cache (empty if none).

    Each report run atomically replaces its months; garbled lines are skipped, never raised."""
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
                        latest[(str(data["project"]), str(data["date"]))] = float(data["hours"])
                    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                        _LOGGER.warning("Skipping unreadable observed line in %s", path.name)
        except OSError as exc:
            _LOGGER.warning("Could not read observed file %s: %s", path, exc)
    return latest
