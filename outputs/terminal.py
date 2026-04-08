from __future__ import annotations

from collections import defaultdict


def print_source_summary(events, source_order):
    counts = defaultdict(int)
    for event in events:
        counts[event["source"]] += 1
    print("\n── Källsammanfattning (efter filter & dedupe, före sessioner) ──")
    for src in sorted(counts, key=lambda s: source_order.index(s) if s in source_order else 99):
        print(f"  {src}: {counts[src]}")
    print(f"  Summa: {sum(counts.values())}")
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
    print("  TIDLOGGAR — SAMMANSTÄLLNING")
    print(f"{'═' * 64}\n")

    if config_path:
        print(f"Projektkonfig: {config_path}")
    else:
        print("Projektkonfig: legacy fallback från CLI-argument")
    print(f"Lokal tidszon: {local_tz}")
    print(f"Projekt: {', '.join(profile['name'] for profile in profiles)}")
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
        print(f"    Sessioner: {len(payload['sessions'])}  →  estimerat ~{payload['hours']:.1f}h")
        print(f"    Källor:    {', '.join(sources)}")
        print(f"    Projekt:   {', '.join(project_names) if project_names else uncategorized}")
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
                f"({raw_dur:.1f}h, {len(session_events)} händelser, {', '.join(session_projects)})"
            )
            if args.all_events:
                for event in session_events:
                    print(
                        f"        · {event['local_ts'].strftime('%H:%M:%S')}  "
                        f"[{event['source']}] [{event['project']}]  {event['detail']}"
                    )
            else:
                shown = []
                for event in session_events:
                    marker = f"{event['project']} | {event['detail']}"
                    if marker in shown:
                        continue
                    print(
                        f"        · {event['local_ts'].strftime('%H:%M')}  "
                        f"[{event['source']}] [{event['project']}]  {event['detail']}"
                    )
                    shown.append(marker)
                    if len(shown) >= 5:
                        remaining = len(session_events) - len(shown)
                        if remaining > 0:
                            print(f"          … och {remaining} till")
                        break
        print()

    print(sep)
    print(f"  TOTALT ESTIMERAT (råtid):  ~{total_h:.1f}h")
    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours_fn(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        print(
            f"  FAKTURERBAR SUMMA (per projekt, upp till {args.billable_unit:g} h):  ~{grand_billable:.2f}h"
        )
    if screen_time_days is not None:
        screen_total_h = sum(screen_time_days.values()) / 3600
        print(f"  SCREEN TIME TOTALT: ~{screen_total_h:.1f}h")
        print(f"  DELTA:              {total_h - screen_total_h:+.1f}h")
    print(sep)
    print()

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer = defaultdict(list)
    for project_name in sorted(project_reports):
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    print("Per kund:")
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
            print(f"  - {customer_name}: ~{cust_b:.2f}h fakturerbart (råtid ~{customer_hours:.1f}h)")
        else:
            print(f"  - {customer_name}: ~{customer_hours:.1f}h")
        for project_name in customer_projects:
            hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            days = len(project_reports[project_name])
            if args.billable_unit and args.billable_unit > 0:
                hb = billable_total_hours_fn(hours, args.billable_unit)
                print(f"      · {project_name}: ~{hb:.2f}h fakturerbart (råtid ~{hours:.1f}h) över {days} dagar")
            else:
                print(f"      · {project_name}: ~{hours:.1f}h över {days} dagar")
    print()
    print("  OBS: Totalen ovan är den sammanlagda tidslinjen över alla källor.")
    print(
        "  [Cursor] = Cursor IDE-loggar. [Cursor checkpoints] = Cursor-appens metadata."
        " [Codex IDE] = OpenAI:s Codex-app (~/.codex) — eget program, inte Cursor."
    )
    print("  Kör med --source-summary om du vill se exakt antal händelser per källa efter filter.")
    print(
        f"  Sessioner: luckor kortare än {args.gap_minutes} min räknas som samma pass; "
        f"Chrome tunnas (--chrome-collapse-minutes={args.chrome_collapse_minutes}, 0=av)."
    )
    if args.billable_unit and args.billable_unit > 0:
        print(
            f"  Fakturerbar avrundning: råtid summeras per projekt, sedan avrundas uppat (ceil) "
            f"till närmaste {args.billable_unit:g} h — inte per session."
        )
    print("  Timmar bygger på diskreta händelser (t.ex. Chrome-besök), inte på KnowledgeC per klick.")
    print("  Per projekt räknas på projektmärkta händelser och kan avvika från totalen.")
    print("  Worklog tolkas nu i lokal tid i stället för UTC.")
    if not args.include_uncategorized:
        print("  Oklassade händelser exkluderas från rapporten som standard.")
    if screen_time_days is not None:
        print("  Screen Time kommer från KnowledgeC app-usage och är en jämförelsesignal, inte facit.")
    print()
