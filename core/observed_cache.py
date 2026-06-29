"""Local cache of observed (pre-approval) hours per project+day.

Written as a cheap byproduct of report runs so the agent statusline can compute
``unreported = observed − handled`` without running collectors (Part A of
``docs/task-prompts/gittan-statusline-task.md``).

Mirrors ``core/reported_time.py``: append-only monthly JSONL under
``~/.gittan/observed/YYYY-MM.jsonl``, latest write per ``(project, day)`` wins.
Observed hours are computed with the **same** aggregation the reported layer uses
(``core/reported_sync.py::build_reported_proposals``), so ``observed − handled``
is apples-to-apples against ``core/reported_time.py``.
"""

from __future__ import annotations

import json
import logging
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

    Returns the number of rows written. Idempotent by latest-write-wins: re-running
    a report for the same window appends fresh rows that supersede the old ones.
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
        with _month_path(base, month).open("a", encoding="utf-8") as fh:
            for row in sorted(rows, key=lambda r: (r["date"], r["project"])):
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                written += 1
    return written


def observed_hours_by_project_day(home: Optional[Path] = None) -> Dict[Tuple[str, str], float]:
    """Latest observed hours per ``(project, day)`` from the cache (empty if none).

    Append-only with latest-write-wins, mirroring the reported store; garbled lines
    are skipped, never raised."""
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
