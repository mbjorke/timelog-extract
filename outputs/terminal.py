from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence


def pick_session_preview_events(
    session_events: Sequence[Dict[str, Any]],
    source_order: Sequence[str],
    max_lines: int = 5,
) -> List[Dict[str, Any]]:
    """
    Pick up to max_lines events to print for a session: prefer at least one distinct
    line per source (first chronological hit per source), then fill remaining slots
    in time order with distinct project|detail markers.
    """
    ordered = sorted(session_events, key=lambda e: e["local_ts"])
    sources_seen: List[str] = []
    for ev in ordered:
        if ev["source"] not in sources_seen:
            sources_seen.append(ev["source"])
    sources_by_order = sorted(
        sources_seen,
        key=lambda s: source_order.index(s) if s in source_order else 99,
    )
    markers = set()
    picked: List[Dict[str, Any]] = []

    def try_add(event: Dict[str, Any]) -> bool:
        marker = f"{event['project']} | {event['detail']}"
        if marker in markers:
            return False
        markers.add(marker)
        picked.append(event)
        return True

    for src in sources_by_order:
        if len(picked) >= max_lines:
            break
        for event in ordered:
            if event["source"] != src:
                continue
            if try_add(event):
                break

    for event in ordered:
        if len(picked) >= max_lines:
            break
        try_add(event)

    return picked


def print_source_summary(events, source_order):
    counts = defaultdict(int)
    for event in events:
        counts[event["source"]] += 1
    print("\n── Source summary (after filter & dedupe, before sessions) ──")
    for src in sorted(counts, key=lambda s: source_order.index(s) if s in source_order else 99):
        print(f"  {src}: {counts[src]}")
    print(f"  Total: {sum(counts.values())}")
    print("──\n")


def print_report(
    overall_days,
    project_reports,
    screen_time_days,
    profiles,
    args,
    config_path,
    local_tz,
    source_order,
    uncategorized,
    session_duration_hours_fn,
    billable_total_hours_fn,
):
    sep = "─" * 64
    print(f"\n{'═' * 64}")
    print("  TIMELOGS — SUMMARY")
    print(f"{'═' * 64}\n")

    if config_path:
        print(f"Project config: {config_path}")
    else:
        print("Project config: legacy fallback from CLI arguments")
    print(f"Local timezone: {local_tz}")
    print(f"Projects: {', '.join(profile['name'] for profile in profiles)}")
    print()

    total_h = 0.0
    for day in sorted(overall_days):
        payload = overall_days[day]
        total_h += payload["hours"]
        entries = sorted(payload["entries"], key=lambda x: x["local_ts"])
        sources = sorted(
            {event["source"] for event in entries},
            key=lambda source: source_order.index(source) if source in source_order else 99,
        )
        project_names = sorted({event["project"] for event in entries if event["project"] != uncategorized})
        print(f"📅  {day}")
        print(f"    Sessions: {len(payload['sessions'])}  →  estimated ~{payload['hours']:.1f}h")
        print(f"    Sources:  {', '.join(sources)}")
        print(f"    Projects: {', '.join(project_names) if project_names else uncategorized}")
        if screen_time_days is not None:
            screen_h = screen_time_days.get(day, 0.0) / 3600
            delta = payload["hours"] - screen_h
            print(f"    Screen Time: ~{screen_h:.1f}h  (delta {delta:+.1f}h)")

        for idx, (start_ts, end_ts, session_events) in enumerate(payload["sessions"], 1):
            raw_dur = session_duration_hours_fn(
                session_events, start_ts, end_ts, args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})
            print(
                f"    [{idx}] {start_ts.strftime('%H:%M')}–{end_ts.strftime('%H:%M')} "
                f"({raw_dur:.1f}h, {len(session_events)} events, {', '.join(session_projects)})"
            )
            if args.all_events:
                for event in session_events:
                    print(
                        f"        · {event['local_ts'].strftime('%H:%M:%S')}  "
                        f"[{event['source']}] [{event['project']}]  {event['detail']}"
                    )
            else:
                preview = pick_session_preview_events(session_events, source_order, max_lines=5)
                for event in preview:
                    print(
                        f"        · {event['local_ts'].strftime('%H:%M')}  "
                        f"[{event['source']}] [{event['project']}]  {event['detail']}"
                    )
                if len(preview) < len(session_events):
                    remaining = len(session_events) - len(preview)
                    print(f"          … and {remaining} more")
        print()

    print(sep)
    print(f"  TOTAL ESTIMATED (raw):  ~{total_h:.1f}h")
    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours_fn(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        print(
            f"  BILLABLE TOTAL (per project, up to {args.billable_unit:g} h):  ~{grand_billable:.2f}h"
        )
    if screen_time_days is not None:
        screen_total_h = sum(screen_time_days.values()) / 3600
        print(f"  SCREEN TIME TOTAL: ~{screen_total_h:.1f}h")
        print(f"  DELTA:               {total_h - screen_total_h:+.1f}h")
    print(sep)
    print()

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer = defaultdict(list)
    for project_name in sorted(project_reports):
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    print("By customer:")
    for customer_name in sorted(projects_by_customer, key=lambda name: name.lower()):
        customer_projects = projects_by_customer[customer_name]
        customer_hours = sum(
            sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            for project_name in customer_projects
        )
        if args.billable_unit and args.billable_unit > 0:
            cust_b = sum(
                billable_total_hours_fn(
                    sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                    args.billable_unit,
                )
                for pn in customer_projects
            )
            print(f"  - {customer_name}: ~{cust_b:.2f}h billable (raw ~{customer_hours:.1f}h)")
        else:
            print(f"  - {customer_name}: ~{customer_hours:.1f}h")
        for project_name in customer_projects:
            hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            days = len(project_reports[project_name])
            if args.billable_unit and args.billable_unit > 0:
                hb = billable_total_hours_fn(hours, args.billable_unit)
                print(f"      · {project_name}: ~{hb:.2f}h billable (raw ~{hours:.1f}h) over {days} day(s)")
            else:
                print(f"      · {project_name}: ~{hours:.1f}h over {days} day(s)")
    print()
    print("  Note: The total above is the combined timeline across all sources.")
    print(
        "  [Cursor] = Cursor IDE logs. [Cursor checkpoints] = Cursor app metadata."
        " [Codex IDE] = OpenAI Codex app (~/.codex) — separate from Cursor."
    )
    print("  Use --source-summary for exact event counts per source after filtering.")
    print(
        f"  Sessions: gaps shorter than {args.gap_minutes} min count as one block; "
        f"Chrome is collapsed (--chrome-collapse-minutes={args.chrome_collapse_minutes}, 0=off)."
    )
    if args.billable_unit and args.billable_unit > 0:
        print(
            f"  Billable rounding: raw time is summed per project, then rounded up (ceil) "
            f"to the nearest {args.billable_unit:g} h — not per session."
        )
    print("  Hours are based on discrete events (e.g. Chrome visits), not KnowledgeC per click.")
    print("  Per-project totals use classified events and may differ from the headline total.")
    print("  Worklog timestamps are interpreted in local time, not UTC.")
    if not args.include_uncategorized:
        print("  Uncategorized events are excluded from the report by default.")
    if screen_time_days is not None:
        print("  Screen Time comes from KnowledgeC app usage; it is a comparison signal, not ground truth.")
    print()
