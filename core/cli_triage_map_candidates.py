"""Aggregate URL-key candidates for `gittan triage-map` (keeps CLI module under CI line limits)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from collectors.chrome import chrome_ts
from core.chrome_epoch import CHROME_EPOCH_DELTA_US
from core.cli_triage import _filter_triage_noise_rows
from core.domain import classify_project
from scripts.calibration.gap_day_triage import fetch_chrome_rows_for_day

_URL_RE = re.compile(r"https?://\S+")
UNCATEGORIZED = "Uncategorized"
URL_FIRST_SOURCES = {"Chrome", "Lovable (desktop)"}


@dataclass
class UrlCandidate:
    title: str
    url_key: str
    suggested_project: str
    confidence_label: str
    confidence_score: float
    impact_hours: float
    events: int
    days: int
    last_seen: str
    sample_urls: list[str]


def _confidence_rank(label: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(label).strip().lower(), 3)


def _split_title_url(detail: str) -> tuple[str, str]:
    text = str(detail or "").strip()
    if not text:
        return "", ""
    if " — " in text:
        left, right = text.split(" — ", 1)
        m = _URL_RE.search(right)
        if m:
            return left.strip(), m.group(0).strip()
    m = _URL_RE.search(text)
    if m:
        title = text[: m.start()].strip(" -—") or "Untitled"
        return title, m.group(0).strip()
    return text, ""


def _url_key(url: str) -> str:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    segments = [seg for seg in p.path.split("/") if seg]
    if host == "github.com" and len(segments) >= 2:
        return f"{host}/{segments[0]}/{segments[1]}"
    if host == "pypi.org" and len(segments) >= 2 and segments[0] == "project":
        return f"{host}/{segments[0]}/{segments[1]}"
    if segments:
        return f"{host}/{segments[0]}"
    return host


def _is_valid_url_key(key: str) -> bool:
    text = str(key or "").strip().lower()
    if not text or "." not in text:
        return False
    host = text.split("/", 1)[0]
    if host.endswith(".lovableproject.com"):
        return False
    if host.startswith("api.individual.githubcopilot.com"):
        return False
    return True


def _confidence_label(score: float, events: int) -> str:
    if score >= 0.8 and events >= 3:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def build_url_candidates(
    *,
    report,
    profiles: list[dict[str, Any]],
    max_rows: int,
    min_events: int = 2,
    include_low_signal: bool = False,
) -> list[UrlCandidate]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "titles": Counter(),
            "urls": Counter(),
            "project_votes": Counter(),
            "events": 0,
            "days": set(),
            "last_seen": None,
        }
    )
    for event in list(getattr(report, "included_events", []) or []):
        source = str(event.get("source", "")).strip()
        if source not in URL_FIRST_SOURCES:
            continue
        if str(event.get("project", "")).strip() != UNCATEGORIZED:
            continue
        title, url = _split_title_url(str(event.get("detail", "")))
        if not url:
            continue
        key = _url_key(url)
        if not include_low_signal and not _is_valid_url_key(key):
            continue
        bucket = grouped[key]
        bucket["events"] += 1
        bucket["titles"][title or "Untitled"] += 1
        bucket["urls"][url] += 1
        ts = event.get("timestamp")
        if isinstance(ts, datetime):
            bucket["days"].add(ts.date().isoformat())
            last_seen = bucket["last_seen"]
            if last_seen is None or ts > last_seen:
                bucket["last_seen"] = ts
        predicted = classify_project(f"{title} {url}", profiles, UNCATEGORIZED)
        if predicted and predicted != UNCATEGORIZED:
            bucket["project_votes"][predicted] += 1

    candidates: list[UrlCandidate] = []
    for key, bucket in grouped.items():
        events = int(bucket["events"])
        if not include_low_signal and events < max(1, int(min_events)):
            continue
        top_title = bucket["titles"].most_common(1)[0][0] if bucket["titles"] else "Untitled"
        votes = bucket["project_votes"]
        if votes:
            suggested, top_votes = votes.most_common(1)[0]
            confidence_score = float(top_votes) / float(events)
            suggested_project = str(suggested)
        else:
            confidence_score = 0.0
            suggested_project = UNCATEGORIZED
        candidates.append(
            UrlCandidate(
                title=top_title,
                url_key=key,
                suggested_project=suggested_project,
                confidence_label=_confidence_label(confidence_score, events),
                confidence_score=confidence_score,
                impact_hours=0.0,
                events=events,
                days=len(bucket["days"]),
                last_seen=(
                    bucket["last_seen"].astimezone().strftime("%Y-%m-%d")
                    if isinstance(bucket["last_seen"], datetime)
                    else "-"
                ),
                sample_urls=[u for u, _n in bucket["urls"].most_common(3)],
            )
        )
    candidates.sort(key=lambda row: (_confidence_rank(row.confidence_label), -row.confidence_score, -row.events, row.url_key))
    return candidates[: max(1, int(max_rows))]


def build_url_candidates_from_gap_days(
    *,
    day_unexplained_hours: dict[str, float],
    profiles: list[dict[str, Any]],
    max_rows: int,
    min_events: int = 2,
    include_low_signal: bool = False,
) -> list[UrlCandidate]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "titles": Counter(),
            "project_votes": Counter(),
            "events": 0,
            "days": set(),
            "last_seen": None,
            "impact_hours": 0.0,
        }
    )
    for day in sorted(day_unexplained_hours.keys()):
        rows = fetch_chrome_rows_for_day(day, home=Path.home())
        signal_rows, _ = _filter_triage_noise_rows(rows)
        if not signal_rows:
            continue
        per_key_counts: Counter[str] = Counter()
        row_data: list[tuple[datetime, str, str]] = []
        for visit_time_cu, url, title in signal_rows:
            key = _url_key(str(url))
            if not include_low_signal and not _is_valid_url_key(key):
                continue
            ts = chrome_ts(int(visit_time_cu), CHROME_EPOCH_DELTA_US)
            per_key_counts[key] += 1
            row_data.append((ts, str(url), str(title)))
        total_count = sum(per_key_counts.values())
        if total_count <= 0:
            continue
        day_hours = float(day_unexplained_hours.get(day, 0.0) or 0.0)
        per_key_impact_hours = {
            key: day_hours * (float(count) / float(total_count))
            for key, count in per_key_counts.items()
        }
        for ts, url, title in row_data:
            key = _url_key(str(url))
            bucket = grouped[key]
            bucket["events"] += 1
            bucket["titles"][str(title or "Untitled")] += 1
            bucket["days"].add(ts.date().isoformat())
            if bucket["last_seen"] is None or ts > bucket["last_seen"]:
                bucket["last_seen"] = ts
            predicted = classify_project(f"{title} {url}", profiles, UNCATEGORIZED)
            if predicted and predicted != UNCATEGORIZED:
                bucket["project_votes"][predicted] += 1
        for key, impact in per_key_impact_hours.items():
            grouped[key]["impact_hours"] += impact

    candidates: list[UrlCandidate] = []
    for key, bucket in grouped.items():
        events = int(bucket["events"])
        if not include_low_signal and events < max(1, int(min_events)):
            continue
        top_title = bucket["titles"].most_common(1)[0][0] if bucket["titles"] else "Untitled"
        votes = bucket["project_votes"]
        if votes:
            suggested, top_votes = votes.most_common(1)[0]
            confidence_score = float(top_votes) / float(events)
            suggested_project = str(suggested)
        else:
            confidence_score = 0.0
            suggested_project = UNCATEGORIZED
        candidates.append(
            UrlCandidate(
                title=top_title,
                url_key=key,
                suggested_project=suggested_project,
                confidence_label=_confidence_label(confidence_score, events),
                confidence_score=confidence_score,
                impact_hours=float(bucket.get("impact_hours", 0.0) or 0.0),
                events=events,
                days=len(bucket["days"]),
                last_seen=(
                    bucket["last_seen"].astimezone().strftime("%Y-%m-%d")
                    if isinstance(bucket["last_seen"], datetime)
                    else "-"
                ),
                sample_urls=[],
            )
        )
    candidates.sort(key=lambda row: (_confidence_rank(row.confidence_label), -row.confidence_score, -row.events, row.url_key))
    return candidates[: max(1, int(max_rows))]


def _auto_assign_high(rows: list[UrlCandidate], project_names: list[str]) -> dict[str, str]:
    allowed = set(project_names)
    out: dict[str, str] = {}
    for row in rows:
        if row.confidence_label != "high":
            continue
        suggested = str(row.suggested_project or "").strip()
        if not suggested or suggested == UNCATEGORIZED:
            continue
        if suggested in allowed:
            out[row.url_key] = suggested
    return out
