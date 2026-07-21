#!/usr/bin/env python3
"""Render a same-day Timely-vs-Gittan ledger side by side for demo/partner use.

Left column: Timely Memory spans (what their capture saw).
Right column: Gittan sessions with structure (project, sources, event count).

Inputs are the ledger-benchmark exports (see
docs/runbooks/timely-gittan-event-ledger-benchmark.md):
    private/benchmarks/gittan-<DAY>.json          (gittan truth payload)
    private/benchmarks/timely-<DAY>-memories.tsv  (start_utc, end_utc, seconds,
                                                   app_name, window_title, url)

Usage:
    python3 scripts/render_ledger_sidebyside.py --day 2026-07-03
    python3 scripts/render_ledger_sidebyside.py --day 2026-07-03 \
        --from-hour 12 --to-hour 16          # zoom into a window
    python3 scripts/render_ledger_sidebyside.py --day 2026-07-03 --mask

--mask pseudonymizes project names (Client A, Client B, ...) and blanks
window titles that contain person-like names. Default shows real data:
this is the operator's own machine and their call — but masking is one
flag away if screen-sharing turns out wider than expected.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BENCH = Path("private/benchmarks")
MIN_SPAN_S = 120  # hide micro-spans on the Timely side; keeps the view calm


def load_timely(day: str, tz=None):
    """Load Timely spans, converting UTC to ``tz``.

    ``tz`` must be the same zone the Gittan sessions use (the report's local
    offset), or the two columns and the hour-window filter misalign whenever
    the machine's timezone differs from the export's. Falls back to system
    local only when no target tz is available.
    """
    spans = []
    with open(BENCH / f"timely-{day}-memories.tsv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            secs = int(float(row["seconds"]))
            if secs < MIN_SPAN_S:
                continue
            start = datetime.fromisoformat(row["start_utc"]).replace(tzinfo=timezone.utc)
            spans.append(
                {
                    "start": start.astimezone(tz),
                    "end": (start + timedelta(seconds=secs)).astimezone(tz),
                    "app": row["app_name"],
                    "title": row["window_title"],
                }
            )
    spans.sort(key=lambda s: s["start"])
    return spans


def load_gittan(day: str):
    payload = json.loads((BENCH / f"gittan-{day}.json").read_text(encoding="utf-8"))
    sessions = []
    for sess in payload["days"][day]["sessions"]:
        projects = Counter(e["project"] for e in sess["events"])
        sources = Counter(e["source"] for e in sess["events"])
        sessions.append(
            {
                "start": datetime.fromisoformat(sess["start_local"]),
                "end": datetime.fromisoformat(sess["end_local"]),
                "hours": sess["hours_estimated"],
                "events": sess["event_count"],
                "projects": projects,
                "sources": sources,
            }
        )
    sessions.sort(key=lambda s: s["start"])
    return sessions


def _client_label(n: int) -> str:
    """Excel-style A, B, ... Z, AA, AB, ... so it stays readable past 26."""
    label = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(ord("A") + rem) + label
    return f"Client {label}"


def build_masker(sessions):
    """Stable pseudonyms per project name, assigned in first-seen order."""
    mapping = {}
    for sess in sessions:
        for name in sess["projects"]:
            if name not in mapping and name != "Uncategorized":
                mapping[name] = _client_label(len(mapping))
    mapping["Uncategorized"] = "Uncategorized"
    return mapping


def fmt_range(start, end):
    return f"{start:%H:%M}-{end:%H:%M}"


def render(day, spans, sessions, mask, from_hour, to_hour):
    def in_window(start, end):
        # True interval overlap with [from_hour, to_hour): keep anything that
        # touches the window, including a session that started just before it
        # (start-hour-only checks drop those when zooming into a short call).
        start_h = start.hour + start.minute / 60
        end_h = end.hour + end.minute / 60
        return start_h < to_hour and end_h > from_hour

    name_map = build_masker(sessions) if mask else {}

    def project_label(name):
        return name_map.get(name, name) if mask else name

    left = []
    for span in spans:
        if not in_window(span["start"], span["end"]):
            continue
        title = span["title"]
        if mask and title not in ("", span["app"]):
            title = "(title hidden)"
        label = span["app"] if title in ("", span["app"]) else f"{span['app']}: {title}"
        left.append(f"{fmt_range(span['start'], span['end'])}  {label[:44]}")

    right = []
    for sess in sessions:
        if not in_window(sess["start"], sess["end"]):
            continue
        top_projects = ", ".join(
            f"{project_label(p)} ({n})" for p, n in sess["projects"].most_common(2)
        )
        top_sources = ", ".join(s for s, _ in sess["sources"].most_common(3))
        right.append(
            f"{fmt_range(sess['start'], sess['end'])}  {sess['hours']:.2f}h  "
            f"{sess['events']} ev  {top_projects}"
        )
        right.append(f"             sources: {top_sources[:40]}")

    width = 48
    print(f"\n  {day}  ({from_hour:02d}:00-{to_hour:02d}:00 local)")
    print(f"  {'TIMELY MEMORY (presence spans)':<{width}}  GITTAN (structured sessions)")
    print(f"  {'-' * width}  {'-' * width}")
    for i in range(max(len(left), len(right))):
        left_cell = left[i] if i < len(left) else ""
        right_cell = right[i] if i < len(right) else ""
        print(f"  {left_cell:<{width}}  {right_cell}")
    print(
        f"\n  left: {len(left)} spans >= {MIN_SPAN_S // 60} min   "
        f"right: {sum(1 for s in sessions if in_window(s['start'], s['end']))} sessions"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (closed day)")
    ap.add_argument("--from-hour", type=int, default=6)
    ap.add_argument("--to-hour", type=int, default=22)
    ap.add_argument("--mask", action="store_true", help="pseudonymize projects/titles")
    ns = ap.parse_args()

    try:
        datetime.strptime(ns.day, "%Y-%m-%d")
    except ValueError:
        ap.error(f"--day must be YYYY-MM-DD, got {ns.day!r}")
    if not (0 <= ns.from_hour < ns.to_hour <= 24):
        ap.error(f"need 0 <= --from-hour < --to-hour <= 24, got {ns.from_hour}..{ns.to_hour}")
    for suffix in (f"gittan-{ns.day}.json", f"timely-{ns.day}-memories.tsv"):
        if not (BENCH / suffix).exists():
            ap.error(f"missing export: {BENCH / suffix} (run the ledger benchmark for {ns.day} first)")

    sessions = load_gittan(ns.day)
    # Anchor both columns to the report's local zone (carried on the Gittan
    # session timestamps), not the machine's, so times and the hour window
    # line up regardless of where the renderer runs.
    target_tz = sessions[0]["start"].tzinfo if sessions else None
    spans = load_timely(ns.day, tz=target_tz)
    render(ns.day, spans, sessions, ns.mask, ns.from_hour, ns.to_hour)


if __name__ == "__main__":
    main()
