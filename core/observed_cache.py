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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.config import gittan_data_dir
from scripts.reconcile_signatures import (
    DEFAULT_SHIFT_DOMINANCE,
    RE_ATTRIBUTION,
    compare_hours,
)

if TYPE_CHECKING:
    from core.report_service import ReportPayload

_LOGGER = logging.getLogger(__name__)

# Match ``scripts/reconcile_snapshot.py`` CLI defaults so the report nudge and
# the offline instrument name the same failure mode for the same numbers.
REATTRIBUTION_TOLERANCE_PCT = 5.0
REATTRIBUTION_NOISE_FLOOR_HOURS = 0.25


def observed_base_dir(home: Optional[Path] = None) -> Path:
    """Store root: ``~/.gittan/observed`` (local, never uploaded).

    Resolved by :func:`core.config.gittan_data_dir`, so ``$GITTAN_HOME`` relocates
    this cache like every other store (GH-549). It ignored the variable before,
    which meant a sandboxed run still merged into the operator's real cache — and
    that merge is keep-max, so there is no undo.
    """
    return gittan_data_dir(home) / "observed"


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


def report_project_day_hours(report: "ReportPayload") -> Dict[Tuple[str, str], float]:
    """Per-``(project, day)`` hours for this report (same aggregation as the cache)."""
    from core.reported_sync import build_reported_proposals

    totals: Dict[Tuple[str, str], float] = {}
    for proposal in build_reported_proposals(report):
        key = (proposal.project, proposal.date)
        totals[key] = totals.get(key, 0.0) + float(proposal.hours)
    return totals


def _hours_by_day(
    totals: Dict[Tuple[str, str], float],
) -> Dict[str, Dict[str, float]]:
    by_day: Dict[str, Dict[str, float]] = {}
    for (project, day), hours in totals.items():
        by_day.setdefault(day, {})[project] = float(hours)
    return by_day


def _is_coverage_swap(losers: List[Any], gainers: List[Any], noise_floor_hours: float) -> bool:
    """True when movers are only stored-only losers and current-only gainers.

    The observed cache is keep-max per ``(project, day)``, so a day's stored map
    can be a synthetic union of peaks from different report coverages. Comparing
    that union to a later run with a different project set looks like
    re-attribution even though no earlier report held that combined split.
    Skip the pure coverage-swap shape; keep real shuffles where a gainer already
    had baseline hours or a loser still has comparison hours (GH-544).
    """
    if not losers or not gainers:
        return False
    losers_absent = all(float(row.comparison) <= noise_floor_hours for row in losers)
    gainers_new = all(float(row.baseline) <= noise_floor_hours for row in gainers)
    return losers_absent and gainers_new


def detect_reattribution(
    current: Dict[Tuple[str, str], float],
    stored: Dict[Tuple[str, str], float],
    *,
    tolerance_pct: float = REATTRIBUTION_TOLERANCE_PCT,
    noise_floor_hours: float = REATTRIBUTION_NOISE_FLOOR_HOURS,
    shift_dominance: float = DEFAULT_SHIFT_DOMINANCE,
) -> List[Dict[str, Any]]:
    """Find days where the current split re-attributes hours vs the observed cache.

    Uses the same shift-share signature as ``scripts/reconcile_signatures``
    (GH-544 scenario 3). Read-only: does not write the cache.
    """
    if not current or not stored:
        return []
    current_by_day = _hours_by_day(current)
    stored_by_day = _hours_by_day(stored)
    findings: List[Dict[str, Any]] = []
    for day in sorted(set(current_by_day) & set(stored_by_day)):
        baseline = stored_by_day[day]
        comparison = current_by_day[day]
        if not baseline or not comparison:
            continue
        # Filtered / narrower reports omit projects that are still in the sidecar.
        # Restrict to the current project set so omitted projects are not treated
        # as losers that "moved" into the filtered subset.
        current_projects = set(comparison)
        stored_projects = set(baseline)
        if current_projects and current_projects < stored_projects:
            baseline = {name: baseline[name] for name in current_projects}
            comparison = {name: comparison[name] for name in current_projects}
        pair = compare_hours(
            baseline,
            comparison,
            baseline_label="observed",
            comparison_label="rescan",
            tolerance_pct=tolerance_pct,
            noise_floor_hours=noise_floor_hours,
            shift_dominance=shift_dominance,
        )
        if pair.signature != RE_ATTRIBUTION:
            continue
        movers = pair.movers()
        losers = [row for row in movers if row.delta < 0]
        gainers = [row for row in movers if row.delta > 0]
        # Re-attribution requires both a drop and a gain (hours changing hands).
        if not losers or not gainers:
            continue
        if _is_coverage_swap(losers, gainers, noise_floor_hours):
            continue
        findings.append(
            {
                "date": day,
                "moved": pair.moved,
                "shift_share": pair.shift_share,
                "net": pair.net,
                "baseline_total": pair.baseline_total,
                "comparison_total": pair.comparison_total,
                "losers": [
                    {
                        "project": row.project,
                        "from": row.baseline,
                        "to": row.comparison,
                    }
                    for row in losers
                ],
                "gainers": [
                    {
                        "project": row.project,
                        "from": row.baseline,
                        "to": row.comparison,
                    }
                    for row in gainers
                ],
            }
        )
    return findings


def detect_reattribution_for_report(
    report: "ReportPayload",
    home: Optional[Path] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Compare this report's per-day split to the last coherent report split.

    Reads ``last_report_split.jsonl`` (overwrite-per-day), not the keep-max
    monthly cache, so independently retained peaks cannot invent a baseline.
    """
    current = report_project_day_hours(report)
    if not current:
        return []
    stored = read_last_report_split(home)
    if not stored:
        return []
    return detect_reattribution(current, stored, **kwargs)


_LAST_REPORT_SPLIT_NAME = "last_report_split.jsonl"


def _last_report_split_path(home: Optional[Path] = None) -> Path:
    return observed_base_dir(home) / _LAST_REPORT_SPLIT_NAME


def read_last_report_split(home: Optional[Path] = None) -> Dict[Tuple[str, str], float]:
    """Last coherent per-``(project, day)`` hours written by a report run.

    Unlike the keep-max monthly cache, each day is replaced wholesale by the
    report that last covered it, so the map is always one real split.
    """
    path = _last_report_split_path(home)
    if not path.is_file():
        return {}
    latest: Dict[Tuple[str, str], float] = {}
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                row = _coerce_row(data)
                if row is None:
                    continue
                latest[(row["project"], row["date"])] = float(row["hours"])
    except OSError as exc:
        _LOGGER.warning("Could not read last report split %s: %s", path, exc)
        return {}
    return latest


def write_last_report_split(
    totals: Dict[Tuple[str, str], float],
    home: Optional[Path] = None,
    *,
    captured_at: Optional[str] = None,
) -> None:
    """Update the coherent split for every day present in ``totals``.

    Days not in ``totals`` are left unchanged. When this report's projects for a
    day are a strict subset of the sidecar's projects for that day, skip the
    day entirely so a filtered run does not become the next full-report
    baseline. Otherwise replace the day wholesale (one coherent report).
    Failures are logged and ignored — this file is advisory for the nudge only.
    """
    if not totals:
        return
    base = observed_base_dir(home)
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _LOGGER.warning("observed cache: could not create %s: %s", base, exc)
        return
    path = _last_report_split_path(home)
    stamp = captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_by_day = _hours_by_day(totals)
    existing_rows: List[dict] = []
    existing_by_day: Dict[str, Dict[str, float]] = {}
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    row = _coerce_row(data)
                    if row is None:
                        continue
                    existing_rows.append(row)
                    existing_by_day.setdefault(row["date"], {})[row["project"]] = float(
                        row["hours"]
                    )
        except OSError as exc:
            _LOGGER.warning("observed cache: could not read last report split: %s", exc)
            return
    skip_days = {
        day
        for day, projects in new_by_day.items()
        if projects
        and day in existing_by_day
        and set(projects) < set(existing_by_day[day])
    }
    replace_days = set(new_by_day) - skip_days
    kept: List[dict] = [row for row in existing_rows if row["date"] not in replace_days]
    for day in sorted(replace_days):
        for project, hours in sorted(new_by_day[day].items()):
            kept.append(
                {
                    "project": project,
                    "date": day,
                    "hours": round(float(hours), 2),
                    "captured_at": stamp,
                }
            )
    fd, temp_path = tempfile.mkstemp(dir=base, prefix=".tmp_split_", suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for row in sorted(kept, key=lambda r: (r["date"], r["project"])):
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    except Exception as exc:  # noqa: BLE001 - advisory sidecar; never block keep-max
        _LOGGER.debug("observed cache: could not write last report split: %s", exc)
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def write_observed_summary(report: "ReportPayload", home: Optional[Path] = None) -> int:
    """Persist per-``(project, day)`` observed hours from a report.

    Returns the number of rows written. Merge is **keep-max** per ``(project, date)``:
    a run can only raise or hold a stored observed value, never lower it, so evidence
    decay on closed months cannot silently degrade the record (see
    ``docs/incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md``).

    Before the keep-max write, compares this run's split to the prior coherent
    ``last_report_split`` and attaches any re-attribution findings on
    ``report.reattribution_vs_observed`` (GH-544 scenario 3). Detection is
    read-only against that sidecar; keep-max behaviour is unchanged. After a
    successful keep-max write, the sidecar is updated for days this report
    covered (subset/filtered days are left unchanged so they do not become the
    next full-report baseline).
    """
    # Detect before keep-max / sidecar write: after those writes the baseline
    # would already match this run and the gainer side of a shuffle would hide.
    findings = detect_reattribution_for_report(report, home=home)
    try:
        report.reattribution_vs_observed = findings  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - advisory only; never block the cache write
        _LOGGER.debug("observed cache: could not attach re-attribution findings: %s", exc)

    totals = report_project_day_hours(report)
    if not totals:
        return 0

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
    write_last_report_split(totals, home=home, captured_at=captured_at)
    return written


def observed_hours_by_project_day(home: Optional[Path] = None) -> Dict[Tuple[str, str], float]:
    """Observed hours per ``(project, day)`` from the cache (empty if none).

    Values are a keep-max high-water mark across report runs; garbled lines are
    skipped, never raised."""
    base = observed_base_dir(home)
    if not base.is_dir():
        return {}
    latest: Dict[Tuple[str, str], float] = {}
    for path in sorted(base.glob("????-??.jsonl")):
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


def observed_lifetime_hours(
    home: Optional[Path] = None,
) -> Tuple[Dict[str, float], Optional[Tuple[str, str]]]:
    """Per-project **ceiling** on hours, and the day window it covers.

    Not a measurement. The cache is keep-max — a run can raise a day's value and
    never lower it — so this sum is the most any run ever detected, including runs
    of versions that over-counted. Callers must not present it as time worked
    (GH-543).

    Sums the per-day rows the cache already holds, so no collector runs and no
    event is re-classified: the expensive part of a report is reading the
    sources, and this deliberately does not.

    The window is returned alongside the totals rather than left to the caller
    to guess. The cache is what survived retention, so "all time" would be a
    claim this data cannot support — a caller that shows the number must be able
    to show what it covers (GH-537).

    Returns ``({}, None)`` when the cache is empty.
    """
    per_day = observed_hours_by_project_day(home)
    if not per_day:
        return {}, None
    totals: Dict[str, float] = {}
    first = last = None
    for (project, day), hours in per_day.items():
        totals[project] = totals.get(project, 0.0) + hours
        if first is None or day < first:
            first = day
        if last is None or day > last:
            last = day
    window = (first, last) if first and last else None
    return totals, window


def observed_last_capture_date(home: Optional[Path] = None) -> Optional[str]:
    """The most recent ``captured_at`` date (``YYYY-MM-DD``) in the cache, or None.

    Lets the statusline distinguish "all reported" from "the cache wasn't refreshed
    today" (i.e. ``gittan report`` hasn't run) so it never claims all-clear on stale
    data."""
    base = observed_base_dir(home)
    if not base.is_dir():
        return None
    latest: Optional[datetime] = None
    for path in sorted(base.glob("????-??.jsonl")):
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
