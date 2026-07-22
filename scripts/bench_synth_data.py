#!/usr/bin/env python3
"""Generate a synthetic, reproducible event dataset for hot-path benchmarking.

Fabricates N events in the exact shape collectors produce (``source``,
``timestamp``, ``detail``) plus a matching synthetic project-profile list, so
the classification + session-math hot path can be benchmarked without touching
any real local data. Seeded for reproducibility.

Usage:
    python scripts/bench_synth_data.py --events 2000 --days 14 --projects 10 \
        --seed 42 --out private/bench/synth_events.json

The output JSON is consumed by scripts/bench_hotpath.py.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCES_AI = [
    "Cursor",
    "Cursor checkpoints",
    "Claude Code CLI",
    "Claude Desktop",
    "Codex IDE",
    "Gemini CLI",
]
SOURCES_PASSIVE = [
    "Chrome",
    "Apple Mail",
    "GitHub",
    "TIMELOG.md",
]

FIRST_WORDS = ["nova", "flux", "orbit", "cedar", "delta", "harbor", "lumen", "quartz", "raven", "sable", "tidal", "verve"]
SECOND_WORDS = ["site", "app", "portal", "shop", "crm", "docs", "board", "sync", "hub", "flow"]
CLIENTS = [
    "Acme Corp",
    "Borealis",
    "Cygnus Media",
    "Delta Builders",
    "Echo Digital",
    "Fjordline",
    "Granite Digital",
    "Harbor Co",
    "Icebreaker Inc",
    "Jade Falcon",
    "Kestrel Labs",
    "Lakeview Co",
]
FILES = [
    "core/pipeline.py",
    "src/index.ts",
    "app/routes.tsx",
    "lib/session.py",
    "styles/main.css",
    "api/handlers.go",
    "tests/test_report.py",
    "README.md",
    "components/Invoice.vue",
    "utils/dates.py",
]
BROWSER_TOPICS = [
    "pricing page",
    "admin dashboard",
    "checkout flow",
    "landing hero",
    "blog draft",
    "API docs",
    "analytics report",
    "settings panel",
]
NOISE_TITLES = [
    "Hacker News — front page",
    "Python typing best practices — Stack Overflow",
    "YouTube — synthwave mix",
    "news.example — headlines",
    "Weather forecast Example City",
    "GitHub Actions pricing — docs",
    "Reddit — r/programming",
    "Wikipedia — Session (computer science)",
]
COMMIT_VERBS = ["fix", "add", "refactor", "polish", "wire up", "remove", "extract", "speed up"]
COMMIT_OBJECTS = [
    "session math",
    "invoice rounding",
    "login form",
    "date parsing",
    "PDF layout",
    "nav menu",
    "config loader",
    "CI workflow",
]
MAIL_TOPICS = ["invoice draft", "status sync", "new feature", "quote request"]

DEFAULT_START_DATE = "2024-01-01"
DEFAULT_TZ = "UTC"


def build_profiles(n_projects: int, rng: random.Random) -> list[dict]:
    profiles = []
    used = set()
    for i in range(n_projects):
        while True:
            slug = f"{rng.choice(FIRST_WORDS)}-{rng.choice(SECOND_WORDS)}"
            if slug not in used:
                used.add(slug)
                break
        client = CLIENTS[i % len(CLIENTS)]
        domain = slug.replace("-", "") + ".example"
        profile = {
            "name": slug,
            "match_terms": [
                slug,
                client.lower(),
                f"workspace/{slug}",
                domain,
                slug.split("-")[0],  # ambiguous short term shared style
            ],
        }
        if rng.random() < 0.4:
            profile["tracked_urls"] = [f"https://{slug}.lovableproject.com"]
        profiles.append({**profile, "_client": client, "_domain": domain})
    return profiles


def make_detail(source: str, profile: dict | None, rng: random.Random) -> str:
    """Build a realistic detail string; profile=None means noise (no project signal)."""
    if profile is None:
        if source == "Chrome":
            return rng.choice(NOISE_TITLES)
        if source == "Apple Mail":
            return "Newsletter: weekly offers"
        return f"scratch: {rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)}"
    slug = profile["name"]
    client = profile["_client"]
    if source in ("Cursor", "Cursor checkpoints", "Codex IDE"):
        return (
            f"Edited {rng.choice(FILES)} — "
            f"/fixture/workspace/project-alpha/{slug}/{rng.choice(FILES)}"
        )
    if source in ("Claude Code CLI", "Claude Desktop", "Gemini CLI"):
        return f"{rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)} for {slug} ({client})"
    if source == "Chrome":
        if profile.get("tracked_urls") and rng.random() < 0.3:
            return f"{slug} preview — https://{slug}.lovableproject.com/edit"
        if rng.random() < 0.2:
            return f"Dashboard ‹ {slug} — WordPress — https://{profile['_domain']}/wp-admin/"
        return f"{rng.choice(BROWSER_TOPICS)} — {profile['_domain']}"
    if source == "Apple Mail":
        return f"Re: {client} — {rng.choice(MAIL_TOPICS)} {slug}"
    if source == "GitHub":
        return f"Pushed to {slug}: {rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)}"
    if source == "TIMELOG.md":
        return f"- {slug}: {rng.choice(COMMIT_OBJECTS)}"
    return f"{slug} activity"


def _day_event_counts(events_target: int, days: int) -> list[int]:
    base, rem = divmod(events_target, days)
    return [base + (1 if i < rem else 0) for i in range(days)]


def _block_event_counts(events_for_day: int, n_blocks: int) -> list[int]:
    if events_for_day <= 0:
        return [0] * n_blocks
    base, rem = divmod(events_for_day, n_blocks)
    return [base + (1 if i < rem else 0) for i in range(n_blocks)]


def _resolve_tz(tz_name: str):
    """Match bench_hotpath: UTC is case-insensitive and uses timezone.utc."""
    name = (tz_name or "UTC").strip()
    if name.upper() == "UTC":
        return timezone.utc, "UTC"
    return ZoneInfo(name), name


def generate(
    events_target: int,
    days: int,
    n_projects: int,
    seed: int,
    *,
    start_date: str = DEFAULT_START_DATE,
    tz_name: str = DEFAULT_TZ,
) -> dict:
    if events_target < 0:
        raise ValueError("events_target must be >= 0")
    if days < 1:
        raise ValueError("days must be >= 1")
    max_projects = len(FIRST_WORDS) * len(SECOND_WORDS)
    if not 1 <= n_projects <= max_projects:
        raise ValueError(f"n_projects must be between 1 and {max_projects}")

    rng = random.Random(seed)
    profiles = build_profiles(n_projects, rng)
    tz, tz_label = _resolve_tz(tz_name)
    day0 = datetime.combine(date.fromisoformat(start_date), datetime.min.time(), tzinfo=tz)

    events: list[dict] = []
    day_counts = _day_event_counts(events_target, days)
    # (source, detail, expected_project) for repeated browser titles
    revisit_pool: list[tuple[str, str, str | None]] = []

    for d, events_for_day in enumerate(day_counts):
        day_start = day0 + timedelta(days=d)
        n_blocks = rng.randint(2, 4)
        block_counts = _block_event_counts(events_for_day, n_blocks)
        cursor_h = 8.0 + rng.random() * 2
        for block_len in block_counts:
            block_projects = rng.sample(profiles, k=min(len(profiles), rng.randint(1, 2)))
            block_len_min = rng.randint(30, 150)
            block_start = day_start + timedelta(hours=cursor_h)
            for _ in range(block_len):
                offset = rng.random() * block_len_min
                ts = block_start + timedelta(minutes=offset)
                roll = rng.random()
                if roll < 0.15:
                    prof = None  # noise
                else:
                    prof = rng.choice(block_projects)
                source = rng.choice(SOURCES_AI if rng.random() < 0.55 else SOURCES_PASSIVE)
                if source == "Chrome" and revisit_pool and rng.random() < 0.25:
                    src, detail, expected = rng.choice(revisit_pool)
                    events.append(
                        {
                            "source": src,
                            "timestamp": ts.isoformat(),
                            "detail": detail,
                            "expected_project": expected,
                        }
                    )
                    continue
                detail = make_detail(source, prof, rng)
                # Ground truth: the profile the detail was built from, or None
                # for noise. Lets a scorer measure classification accuracy
                # instead of only timing the hot path.
                expected = prof["name"] if prof else None
                if source == "Chrome":
                    revisit_pool.append((source, detail, expected))
                events.append(
                    {
                        "source": source,
                        "timestamp": ts.isoformat(),
                        "detail": detail,
                        "expected_project": expected,
                    }
                )
            cursor_h += block_len_min / 60.0 + rng.random() * 2 + 0.5

    events.sort(key=lambda e: e["timestamp"])
    if len(events) != events_target:
        raise AssertionError(
            f"generate() produced {len(events)} events, expected {events_target}"
        )
    clean_profiles = [{k: v for k, v in p.items() if not k.startswith("_")} for p in profiles]
    return {
        "seed": seed,
        "days": days,
        "n_projects": n_projects,
        "start_date": start_date,
        "tz": tz_label,
        "events": events,
        "profiles": clean_profiles,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", type=int, default=2000)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--projects", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        help="ISO date for day 0 (default: 2024-01-01)",
    )
    ap.add_argument(
        "--tz",
        default=DEFAULT_TZ,
        help="IANA timezone for timestamps (default: UTC)",
    )
    ap.add_argument("--out", default="private/bench/synth_events.json")
    ap.add_argument(
        "--emit-config",
        metavar="PATH",
        help="Also write the generated profiles as a usable timelog_projects.json.",
    )
    ns = ap.parse_args()

    data = generate(
        ns.events,
        ns.days,
        ns.projects,
        ns.seed,
        start_date=ns.start_date,
        tz_name=ns.tz,
    )
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"wrote {len(data['events'])} events / {ns.projects} profiles → {out}")

    if ns.emit_config:
        cfg_path = Path(ns.emit_config)
        if cfg_path.exists():
            raise SystemExit(
                f"refusing to overwrite existing config: {cfg_path}\n"
                "Point --emit-config at a new path (project config is critical local data)."
            )
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        emit_profiles = [{**p, "project_id": p["name"]} for p in data["profiles"]]
        cfg_path.write_text(
            json.dumps({"projects": emit_profiles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {len(data['profiles'])} profiles → {cfg_path}")


if __name__ == "__main__":
    main()
