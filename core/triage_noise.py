"""Noise filtering helpers shared by triage flows."""

from __future__ import annotations

from urllib.parse import urlparse

TRIAGE_NOISE_DOMAINS = {
    "cursor.com",
    "www.cursor.com",
    "cursor.sh",
    "www.cursor.sh",
}

TRIAGE_NOISE_TITLE_MARKERS = (
    "canvas sdk mirror failed",
    "skills-cursor",
    "cursor sdk",
    "mcp tool schema",
    "cursor extension host",
    "cursor diagnostics",
)


def extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_triage_noise_row(url: str, title: str) -> bool:
    domain = extract_domain(url)
    if domain in TRIAGE_NOISE_DOMAINS:
        return True
    text = (title or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in TRIAGE_NOISE_TITLE_MARKERS)


def filter_triage_noise_rows(
    chrome_rows: list[tuple[int, str, str]],
) -> tuple[list[tuple[int, str, str]], int]:
    filtered: list[tuple[int, str, str]] = []
    dropped = 0
    for row in chrome_rows:
        _visit_time_cu, url, title = row
        if is_triage_noise_row(url, title):
            dropped += 1
            continue
        filtered.append(row)
    return filtered, dropped
