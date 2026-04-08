"""Rule-based 'executive summary' prose for terminal reports (no LLM)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple


def _project_hours_totals(project_reports: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
    rows = []
    for name, days in project_reports.items():
        h = sum(d["hours"] for d in days.values())
        if h > 0:
            rows.append((name, h))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def _format_project_list(top: List[Tuple[str, float]], limit: int = 3) -> str:
    chunk = top[:limit]
    if not chunk:
        return "uncategorized or mixed activity"
    parts = [f"{name} (~{h:.1f} h)" for name, h in chunk]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def _source_mix(
    included_events: List[Dict[str, Any]], source_order: List[str], limit: int = 4
) -> List[str]:
    counts: Dict[str, int] = defaultdict(int)
    for ev in included_events:
        counts[ev["source"]] += 1

    def sort_key(s: str) -> Tuple[int, int]:
        idx = source_order.index(s) if s in source_order else 999
        return (-counts[s], idx)

    ordered = sorted(counts.keys(), key=sort_key)
    return ordered[:limit]


def build_narrative_lines(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Dict[str, Any]],
    included_events: List[Dict[str, Any]],
    uncategorized: str,
    source_order: List[str],
    dt_from: datetime,
    dt_to: datetime,
) -> List[str]:
    """Return paragraphs (plain English) summarizing the reporting window."""
    days_sorted = sorted(overall_days.keys())
    if not days_sorted:
        return ["No days with activity in this range — nothing to summarize."]

    d0 = days_sorted[0]
    d1 = days_sorted[-1]
    range_lbl = d0 if d0 == d1 else f"{d0} through {d1}"

    total_h = sum(overall_days[d]["hours"] for d in days_sorted)
    n_sess = sum(len(overall_days[d]["sessions"]) for d in days_sorted)
    n_days = len(days_sorted)

    window_start = dt_from.date().isoformat()
    window_end = dt_to.date().isoformat()
    if window_start == window_end == d0 == d1:
        window_note = ""
    elif window_start != window_end:
        window_note = f" (report window {window_start}–{window_end})"
    else:
        window_note = f" (report window {window_start})"

    lines: List[str] = []

    opener = (
        f"In {range_lbl}{window_note}, this run estimates about {total_h:.1f} h of billable "
        f"timeline across {n_days} day(s) and {n_sess} session(s). "
        "Hours come from merged gaps between signals, not stopwatch time."
    )
    lines.append(opener)

    proj_totals = _project_hours_totals(project_reports)
    non_uc = [x for x in proj_totals if x[0] != uncategorized]
    use_totals = non_uc or proj_totals
    if use_totals:
        headline = _format_project_list(use_totals)
        lines.append(f"The biggest slices of time: {headline}.")

    if n_days > 1:
        busiest = max(days_sorted, key=lambda d: overall_days[d]["hours"])
        bh = overall_days[busiest]["hours"]
        bs = len(overall_days[busiest]["sessions"])
        lines.append(f"The busiest calendar day was {busiest} (~{bh:.1f} h, {bs} sessions).")

    mix = _source_mix(included_events, source_order)
    if mix:
        mix_s = ", ".join(mix)
        lines.append(
            f"By raw event counts (after filters), the noisiest sources were: {mix_s}. "
            "That hints where your paper trail was richest, not where time necessarily went."
        )

    lines.append(
        "This blurb is heuristic copy — tweak classifications and session rules, "
        "and the story updates automatically."
    )
    return lines


def print_executive_narrative(lines: List[str]) -> None:
    """Print narrative with a light frame so it stands out in the terminal."""
    sep = "═" * 64
    print(f"\n{sep}")
    print("  EXECUTIVE SUMMARY (rule-based, local)")
    print(sep)
    for block in lines:
        print()
        print(f"  {block}")
    print(f"\n{sep}\n")
