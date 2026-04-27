"""Repository evidence hints for triage review."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

REPO_SUBPATH_MARKERS = {
    "actions",
    "blob",
    "branches",
    "commit",
    "commits",
    "compare",
    "discussions",
    "issues",
    "network",
    "packages",
    "pull",
    "pulls",
    "releases",
    "security",
    "settings",
    "tree",
    "wiki",
}


def build_code_repo_candidates(
    chrome_rows: list[tuple[int, str, str]],
    *,
    limit: int = 5,
) -> list[dict[str, int | str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for _visit_time_cu, url, title in chrome_rows:
        candidate = code_repo_candidate(url, title=title)
        if candidate:
            counts[(candidate["provider"], candidate["value"])] += 1
    return [
        {"provider": provider, "value": value, "visits": visits}
        for (provider, value), visits in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ][:limit]


def code_repo_candidate(url: str, *, title: str = "") -> dict[str, str]:
    github_slug = github_repo_slug(url, title=title)
    if github_slug:
        return {"provider": "github", "value": github_slug}
    return {}


def github_repo_slug(url: str, *, title: str = "") -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return ""
    owner, repo = parts[0].strip(), parts[1].strip()
    has_repo_subpath = len(parts) > 2 and parts[2].lower() in REPO_SUBPATH_MARKERS
    has_repo_title = _title_mentions_repo(title, owner, repo)
    if len(parts) > 2 and not has_repo_subpath:
        return ""
    if len(parts) == 2 and not has_repo_title:
        return ""
    if not _valid_slug_part(owner) or not _valid_slug_part(repo):
        return ""
    return f"github.com/{owner}/{repo}"


def _valid_slug_part(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in {"-", "_", "."} for ch in value)


def _title_mentions_repo(title: str, owner: str, repo: str) -> bool:
    return f"{owner}/{repo}".lower() in (title or "").lower()
