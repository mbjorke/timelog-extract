#!/usr/bin/env python3
"""reconcile_snapshot.py — does a period still report the hours it once reported?

Three views of the same period can disagree, and the disagreement is diagnostic:

1. **snapshot** — a truth payload captured at the time (``core/truth_payload.py``),
   e.g. the JSON written when an invoice was prepared. Frozen; never changes.
2. **observed** — ``<home>/.gittan/observed/<YYYY-MM>.jsonl``, what report runs
   recorded on the days they ran. **Keep-max**: it can only ratchet upward, so a
   value here is an upper bound, not a measurement (GH-543).
3. **rescan** — what a fresh report produces for that period *today*.

For each pair this prints per-project hours and the delta, then names the
signature, because the two failure modes need different fixes:

- **EVIDENCE DECAY** — totals drop together. Sources rotated their history out
  and the events are simply gone. Fix: durable capture (shadow log), not
  classification.
- **RE-ATTRIBUTION** — totals hold while the split moves. The evidence is still
  there; it is being credited to a different project, often a different
  *customer* (GH-544). Fix: attribution, not capture.
- **UPWARD DRIFT** — totals grew without much reallocation. Either better
  detection (new collectors) or a ratchet baked in by keep-max (GH-543); compare
  ``generator.version`` before concluding.
- **MIXED** — both a total change and a large reallocation.

Read-only by construction: it never writes the observed cache and never touches
``timelog_projects.json``. A rescan runs in-process with ``quiet=True`` (the CLI,
not the engine, is what writes the cache) *and* under a throwaway ``GITTAN_HOME``,
so the real cache cannot ratchet as a side effect of measuring it.

PRIVACY: on real data the output carries client names and hours. It is for your
terminal. Use ``--redact`` before pasting anywhere — it replaces project names
with stable ``project-01`` labels and keeps the numbers.

Usage:
    python3 scripts/reconcile_snapshot.py --snapshot PATH
    python3 scripts/reconcile_snapshot.py --period 2026-06
    python3 scripts/reconcile_snapshot.py --snapshot PATH --no-rescan --redact
    python3 scripts/reconcile_snapshot.py --period 2026-06 --json

Exit: 0 = ran (drift may be present), 1 = usage/setup problem,
2 = drift found and ``--fail-on-drift`` was passed.

This module loads the three views and drives the CLI. The comparison model —
the delta decomposition, the signature rules, and the rendering — lives in
``scripts/reconcile_signatures.py``, which touches no files and no clock.
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reconcile_signatures import (
    DEFAULT_SHIFT_DOMINANCE,
    STABLE,
    Hours,
    apply_redaction,
    build_json,
    compare_hours,
    redaction_map,
    render_text,
)

# --------------------------------------------------------------------------
# Loading the three views
# --------------------------------------------------------------------------


def month_bounds(period: str) -> Tuple[str, str]:
    """``"2026-06"`` → ``("2026-06-01", "2026-06-30")``."""
    year, month = (int(part) for part in period.split("-", 1))
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def load_snapshot(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "projects" not in payload:
        raise ValueError(f"{path.name} is not a truth payload (no 'projects' key)")
    # Validate the shape here, where the caller already handles the error and can
    # exit cleanly. Deferring it to snapshot_hours turns a malformed file into an
    # uncaught AttributeError, which for a tool whose output is meant to be trusted
    # is indistinguishable from a crash of its own making.
    projects = payload.get("projects")
    if not isinstance(projects, dict):
        raise ValueError(
            f"{path.name}: 'projects' must be an object, got {type(projects).__name__}"
        )
    for name, hours in projects.items():
        try:
            float(hours if not isinstance(hours, dict) else hours.get("hours_estimated"))
        except (TypeError, ValueError):
            raise ValueError(
                f"{path.name}: project {name!r} has non-numeric hours"
            ) from None
    return payload


def snapshot_hours(payload: Dict[str, Any]) -> Hours:
    projects = payload.get("projects") or {}
    return {str(k): float(v) for k, v in projects.items()}


def snapshot_window(payload: Dict[str, Any]) -> Tuple[str, str]:
    """Local date bounds of the snapshot's ``range`` (dates only, no clock)."""
    rng = payload.get("range") or {}
    start = str(rng.get("from", ""))[:10]
    end = str(rng.get("to", ""))[:10]
    if not start or not end:
        raise ValueError("snapshot has no usable 'range'")
    return start, end


def snapshot_settings(payload: Dict[str, Any]) -> Dict[str, int]:
    settings = payload.get("settings") or {}
    out: Dict[str, int] = {}
    for key in ("gap_minutes", "min_session_minutes", "min_session_passive_minutes"):
        value = settings.get(key)
        if isinstance(value, (int, float)):
            out[key] = int(value)
    return out


def observed_hours(home: Optional[Path], date_from: str, date_to: str) -> Hours:
    """Sum the observed cache for the window. Read-only; opens nothing for writing."""
    from core.observed_cache import observed_hours_by_project_day

    totals: Hours = {}
    for (project, day), hours in observed_hours_by_project_day(home=home).items():
        if date_from <= day <= date_to:
            totals[project] = round(totals.get(project, 0.0) + float(hours), 6)
    return totals


@contextlib.contextmanager
def sandboxed_gittan_home() -> Iterator[Path]:
    """Point ``$GITTAN_HOME`` at a throwaway dir for the duration of a rescan.

    Belt and braces. The engine entrypoint used here does not write the observed
    cache (only ``core/report_cli.py`` does, on non-quiet terminal runs), but any
    state that *does* key off ``$GITTAN_HOME`` — evidence spool, op-logs — lands
    in a temp dir that is deleted afterwards. Resolve the projects config before
    entering: ``$GITTAN_HOME`` also drives config resolution.
    """
    previous = os.environ.get("GITTAN_HOME")
    with tempfile.TemporaryDirectory(prefix="gittan-reconcile-") as tmp:
        os.environ["GITTAN_HOME"] = tmp
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop("GITTAN_HOME", None)
            else:
                os.environ["GITTAN_HOME"] = previous


def resolve_projects_config(explicit: Optional[str]) -> str:
    if explicit:
        return str(Path(explicit).expanduser())
    from core.config import resolve_projects_config_path_and_source

    path, _source = resolve_projects_config_path_and_source()
    return str(path)


def rescan_hours(
    *,
    projects_config: str,
    date_from: str,
    date_to: str,
    settings: Optional[Dict[str, int]] = None,
) -> Hours:
    """Run a fresh report for the window and return per-project hours.

    ``settings`` (from the snapshot) is applied so the comparison isolates
    evidence and attribution rather than a session-math config that changed
    since. ``quiet=True`` keeps the run off the observed-cache write path.
    """
    from core.cli_options import TimelogRunOptions
    from core.report_service import run_timelog_report

    kwargs: Dict[str, Any] = {
        "projects_config": projects_config,
        "date_from": date_from,
        "date_to": date_to,
        "include_uncategorized": True,
        "quiet": True,
        "map_prompt": False,
        "shadow_log": "off",
        "output_format": "json",
    }
    for key, option in (
        ("gap_minutes", "gap_minutes"),
        ("min_session_minutes", "min_session"),
        ("min_session_passive_minutes", "min_session_passive"),
    ):
        if settings and key in settings:
            kwargs[option] = settings[key]
    options = TimelogRunOptions(**kwargs)
    with sandboxed_gittan_home():
        report = run_timelog_report(projects_config, date_from, date_to, options)
    return {
        str(name): round(sum(day["hours"] for day in days.values()), 6)
        for name, days in report.project_reports.items()
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _UsageExitParser(argparse.ArgumentParser):
    """Argument errors exit 1, not 2.

    This module reserves status 2 for --fail-on-drift finding an unstable pair.
    argparse's default of 2 for a typo would make a misinvocation indistinguishable
    from a real finding to anything scripting this tool.
    """

    def error(self, message: str):  # noqa: D102 - argparse contract
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _UsageExitParser(
        prog="reconcile_snapshot.py",
        description="Compare a captured truth payload, the observed cache, and a fresh rescan.",
    )
    parser.add_argument("--snapshot", help="Path to a captured truth payload JSON")
    parser.add_argument("--period", help="YYYY-MM (defaults to the snapshot's range)")
    parser.add_argument("--from", dest="date_from", help="Window start YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="Window end YYYY-MM-DD")
    parser.add_argument(
        "--home",
        help="Home dir holding .gittan/observed (default: your real home, read-only)",
    )
    parser.add_argument("--projects-config", help="Projects config for the rescan")
    parser.add_argument(
        "--no-rescan",
        action="store_true",
        help="Skip the fresh report (compare snapshot vs observed cache only)",
    )
    parser.add_argument(
        "--no-snapshot-settings",
        action="store_true",
        help="Rescan with current defaults instead of the snapshot's session settings",
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=5.0,
        help="Total change within this %% of baseline counts as 'held' (default: 5)",
    )
    parser.add_argument(
        "--noise-floor",
        type=float,
        default=0.25,
        help="Hours below which a change is not worth naming (default: 0.25)",
    )
    parser.add_argument(
        "--shift-dominance",
        type=float,
        default=DEFAULT_SHIFT_DOMINANCE,
        help="Reallocation share above which a residual total change is noise (default: 0.75)",
    )
    parser.add_argument("--redact", action="store_true", help="Replace project names with aliases")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 2 when any pair is not STABLE (for use as a check)",
    )
    return parser


def _validated_window(date_from: str, date_to: str) -> Tuple[str, str]:
    """Both endpoints must be real dates, in order.

    A reversed range selects no rows, which reads as "everything drifted" rather
    than as the usage error it is. An instrument that reports a finding for an
    impossible question is worse than one that refuses to answer.
    """
    try:
        start = date.fromisoformat(date_from)
        end = date.fromisoformat(date_to)
    except ValueError as exc:
        raise ValueError(f"invalid date in window {date_from}..{date_to}: {exc}") from None
    if start > end:
        raise ValueError(f"window starts after it ends: {date_from}..{date_to}")
    return date_from, date_to


def resolve_window(args: argparse.Namespace, snapshot: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    # Half a range is a mistake, not a hint. Falling through to --period or the
    # snapshot would reconcile a window the operator did not ask for and report
    # drift for it successfully — the one failure mode this instrument exists to
    # rule out.
    if bool(args.date_from) != bool(args.date_to):
        raise ValueError("--from and --to must be given together")
    if args.date_from and args.date_to:
        return _validated_window(args.date_from, args.date_to)
    if args.period:
        return _validated_window(*month_bounds(args.period))
    if snapshot is not None:
        # A snapshot's own range is not exempt: a hand-edited or truncated payload
        # can carry a reversed or malformed one just as easily.
        return _validated_window(*snapshot_window(snapshot))
    raise ValueError("need one of --snapshot, --period, or both --from and --to")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    snapshot: Optional[Dict[str, Any]] = None
    if args.snapshot:
        snapshot_path = Path(args.snapshot).expanduser()
        if not snapshot_path.is_file():
            print(f"reconcile_snapshot: no such snapshot: {snapshot_path}", file=sys.stderr)
            return 1
        try:
            snapshot = load_snapshot(snapshot_path)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"reconcile_snapshot: {exc}", file=sys.stderr)
            return 1

    try:
        window = resolve_window(args, snapshot)
    except ValueError as exc:
        print(f"reconcile_snapshot: {exc}", file=sys.stderr)
        return 1

    notes: List[str] = []
    views: Dict[str, Hours] = {}

    if snapshot is not None:
        views["snapshot"] = snapshot_hours(snapshot)
        generator = (snapshot.get("generator") or {}).get("version")
        if generator:
            notes.append(f"snapshot generated by version {generator}")

    home = Path(args.home).expanduser() if args.home else None
    views["observed"] = observed_hours(home, window[0], window[1])
    notes.append("observed is keep-max: an upper bound per day, never a measurement (GH-543)")

    if not args.no_rescan:
        config_path = resolve_projects_config(args.projects_config)
        settings = None
        if snapshot is not None and not args.no_snapshot_settings:
            settings = snapshot_settings(snapshot) or None
            if settings:
                notes.append(f"rescan used the snapshot's session settings: {settings}")
        try:
            views["rescan"] = rescan_hours(
                projects_config=config_path,
                date_from=window[0],
                date_to=window[1],
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001 - report the failure, do not crash the check
            print(f"reconcile_snapshot: rescan failed: {exc}", file=sys.stderr)
            return 1

    if args.redact:
        mapping = redaction_map(views)
        views = {name: apply_redaction(hours, mapping) for name, hours in views.items()}
        notes.append("project names redacted; hours are unchanged")

    order = [name for name in ("snapshot", "observed", "rescan") if name in views]
    # Adjacent pairs tell the story in order; snapshot→rescan is added because the
    # end-to-end drift is the number an invoice would be defended with.
    couples = list(zip(order, order[1:]))
    if len(order) == 3:
        couples.append((order[0], order[2]))
    pairs = [
        compare_hours(
            views[left],
            views[right],
            baseline_label=left,
            comparison_label=right,
            tolerance_pct=args.tolerance_pct,
            noise_floor_hours=args.noise_floor,
            shift_dominance=args.shift_dominance,
        )
        for left, right in couples
    ]
    if not pairs:
        notes.append("only one view available — nothing to reconcile against")

    if args.json:
        print(json.dumps(build_json(window, views, pairs, notes), indent=2, ensure_ascii=False))
    else:
        print(render_text(window, views, pairs, notes), end="")

    if args.fail_on_drift and any(pair.signature != STABLE for pair in pairs):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
