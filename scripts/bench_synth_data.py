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
from datetime import datetime, timedelta
from pathlib import Path

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
CLIENTS = ["Acme AB", "Borealis", "Cygnus Media", "Drakryggen", "Ekens Bygg", "Fjordline", "Granit Digital", "Humlan", "Isbrytaren", "Jaktfalken", "Kastanjen", "Lindqvist & Co"]
FILES = ["core/pipeline.py", "src/index.ts", "app/routes.tsx", "lib/session.py", "styles/main.css", "api/handlers.go", "tests/test_report.py", "README.md", "components/Invoice.vue", "utils/dates.py"]
BROWSER_TOPICS = ["pricing page", "admin dashboard", "checkout flow", "landing hero", "blog draft", "API docs", "analytics report", "settings panel"]
NOISE_TITLES = [
    "Hacker News — front page",
    "Python typing best practices — Stack Overflow",
    "YouTube — synthwave mix",
    "DN.se — nyheter",
    "Weather forecast Stockholm",
    "GitHub Actions pricing — docs",
    "Reddit — r/programming",
    "Wikipedia — Session (computer science)",
]
COMMIT_VERBS = ["fix", "add", "refactor", "polish", "wire up", "remove", "extract", "speed up"]
COMMIT_OBJECTS = ["session math", "invoice rounding", "login form", "date parsing", "PDF layout", "nav menu", "config loader", "CI workflow"]


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
        domain = slug.replace("-", "") + ".se"
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
            return "Nyhetsbrev: veckans erbjudanden"
        return f"scratch: {rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)}"
    slug = profile["name"]
    client = profile["_client"]
    if source in ("Cursor", "Cursor checkpoints", "Codex IDE"):
        return f"Edited {rng.choice(FILES)} — /Users/dev/Workspace/{slug}/{rng.choice(FILES)}"
    if source in ("Claude Code CLI", "Claude Desktop", "Gemini CLI"):
        return f"{rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)} for {slug} ({client})"
    if source == "Chrome":
        if profile.get("tracked_urls") and rng.random() < 0.3:
            return f"{slug} preview — https://{slug}.lovableproject.com/edit"
        if rng.random() < 0.2:
            return f"Dashboard ‹ {slug} — WordPress — https://{profile['_domain']}/wp-admin/"
        return f"{rng.choice(BROWSER_TOPICS)} — {profile['_domain']}"
    if source == "Apple Mail":
        return f"Re: {client} — {rng.choice(['fakturaunderlag', 'avstämning', 'ny funktion', 'offert'])} {slug}"
    if source == "GitHub":
        return f"Pushed to {slug}: {rng.choice(COMMIT_VERBS)} {rng.choice(COMMIT_OBJECTS)}"
    if source == "TIMELOG.md":
        return f"- {slug}: {rng.choice(COMMIT_OBJECTS)}"
    return f"{slug} activity"


def generate(events_target: int, days: int, n_projects: int, seed: int) -> dict:
    rng = random.Random(seed)
    profiles = build_profiles(n_projects, rng)
    local_tz = datetime.now().astimezone().tzinfo

    events: list[dict] = []
    day0 = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    per_day = max(1, events_target // days)

    revisit_pool: list[tuple[str, str]] = []  # (source, detail) for repeated browser titles

    for d in range(days):
        day_start = day0 + timedelta(days=d)
        # 2–4 work blocks per day, each biased to 1–2 projects
        n_blocks = rng.randint(2, 4)
        block_events = per_day // n_blocks
        cursor_h = 8.0 + rng.random() * 2
        for _ in range(n_blocks):
            block_projects = rng.sample(profiles, k=min(len(profiles), rng.randint(1, 2)))
            block_len_min = rng.randint(30, 150)
            block_start = day_start + timedelta(hours=cursor_h)
            for _ in range(block_events):
                offset = rng.random() * block_len_min
                ts = block_start + timedelta(minutes=offset)
                roll = rng.random()
                if roll < 0.15:
                    prof = None  # noise
                else:
                    prof = rng.choice(block_projects)
                source = rng.choice(SOURCES_AI if rng.random() < 0.55 else SOURCES_PASSIVE)
                if source == "Chrome" and revisit_pool and rng.random() < 0.25:
                    src, detail = rng.choice(revisit_pool)
                    events.append({"source": src, "timestamp": ts.isoformat(), "detail": detail})
                    continue
                detail = make_detail(source, prof, rng)
                if source == "Chrome":
                    revisit_pool.append((source, detail))
                events.append({"source": source, "timestamp": ts.isoformat(), "detail": detail})
            cursor_h += block_len_min / 60.0 + rng.random() * 2 + 0.5

    events.sort(key=lambda e: e["timestamp"])
    clean_profiles = [{k: v for k, v in p.items() if not k.startswith("_")} for p in profiles]
    return {
        "seed": seed,
        "days": days,
        "n_projects": n_projects,
        "events": events,
        "profiles": clean_profiles,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", type=int, default=2000)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--projects", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="private/bench/synth_events.json")
    ns = ap.parse_args()

    data = generate(ns.events, ns.days, ns.projects, ns.seed)
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"wrote {len(data['events'])} events / {ns.projects} profiles → {out}")


if __name__ == "__main__":
    main()
