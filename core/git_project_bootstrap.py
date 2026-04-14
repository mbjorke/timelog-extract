"""Git-aware project bootstrap and coverage checks for local onboarding."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.config import as_list


_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".claude",
    ".tmp",
    ".worktrees",
    ".cache",
    ".venv",
    "__pycache__",
    "cache",
    "tmp",
    "temp",
    "vendor",
    "imports",
    "import",
    "worktrees",
    "node_modules",
    "dist",
    "build",
    "Library",
}

_SKIP_PARTIALS = {"cache", "tmp", "temp", "vendor", "import", "worktree"}


@dataclass(frozen=True)
class GitProjectHints:
    repo_root: Path
    repo_name: str
    remote_owner: str
    remote_repo: str
    project_name: str
    customer: str
    match_terms: list[str]


@dataclass(frozen=True)
class MatchTermsCoverage:
    status: str
    detail: str
    suggested_terms: list[str]
    matched_project: str = ""


@dataclass(frozen=True)
class RepoProjectSeed:
    repo_path: Path
    name: str
    customer: str
    match_terms: list[str]
    origin_url: str


@dataclass(frozen=True)
class RepoBootstrapSummary:
    root: Path
    discovered: int
    added: int
    updated: int
    skipped: int
    fallback_used: bool = False


def _run_git(cwd: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _parse_remote(url: str) -> tuple[str, str]:
    cleaned = url.strip()
    if not cleaned:
        return "", ""
    cleaned = cleaned.removesuffix(".git")
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)$", cleaned)
    if match:
        return match.group("owner"), match.group("repo")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", ""


def _keyword_variants(text: str) -> list[str]:
    candidate = text.strip().lower()
    if not candidate:
        return []
    variants = [candidate]
    spaced = re.sub(r"[-_]+", " ", candidate).strip()
    compact = re.sub(r"[-_\s]+", "", candidate).strip()
    if spaced and spaced not in variants:
        variants.append(spaced)
    if compact and compact not in variants and compact != candidate:
        variants.append(compact)
    return variants


def discover_git_project_hints(cwd: Path) -> GitProjectHints | None:
    repo_root_raw = _run_git(cwd, "rev-parse", "--show-toplevel")
    if not repo_root_raw:
        return None
    repo_root = Path(repo_root_raw)
    repo_name = repo_root.name.strip()
    if not repo_name:
        return None
    remote_owner, remote_repo = _parse_remote(_run_git(repo_root, "remote", "get-url", "origin"))
    project_name = remote_repo or repo_name
    customer = remote_owner or project_name
    terms: list[str] = []
    candidates = [project_name]
    if remote_repo and repo_name and repo_name.lower() != remote_repo.lower() and repo_name not in candidates:
        candidates.append(repo_name)
    for candidate in candidates:
        for variant in _keyword_variants(candidate):
            if variant not in terms:
                terms.append(variant)
    if remote_owner and remote_repo:
        slug = f"{remote_owner}/{remote_repo}".lower()
        if slug not in terms:
            terms.append(slug)
    return GitProjectHints(
        repo_root=repo_root,
        repo_name=repo_name,
        remote_owner=remote_owner,
        remote_repo=remote_repo,
        project_name=project_name,
        customer=customer,
        match_terms=terms,
    )


def suggest_bootstrap_root(cwd: Path) -> Path:
    hints = discover_git_project_hints(cwd)
    if hints is not None and hints.repo_root.parent.exists():
        return hints.repo_root.parent
    for candidate in [Path.home() / "Workspace", Path.home() / "Projects", Path.home() / "Code", cwd]:
        if candidate.exists():
            return candidate.resolve()
    return cwd.resolve()


def discover_local_git_repos(root: Path, *, max_depth: int = 2, limit: int = 40) -> list[Path]:
    resolved_root = root.expanduser().resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        return []
    queue: list[tuple[Path, int]] = [(resolved_root, 0)]
    seen: set[Path] = set()
    repos: list[Path] = []
    while queue and len(repos) < limit:
        current, depth = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            has_git_dir = (current / ".git").exists()
        except OSError:
            continue
        if has_git_dir:
            if not any(parent in repos for parent in current.parents):
                repos.append(current)
            continue
        if depth >= max_depth:
            continue
        try:
            children = sorted((child for child in current.iterdir() if child.is_dir()), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            child_name = child.name.lower()
            if child_name.startswith(".") or child.name in _SKIP_DIRS:
                continue
            # Token-aware matching: split by non-alphanumeric delimiters and check whole-token equality
            tokens = re.split(r'[^a-z0-9]+', child_name)
            if any(token in _SKIP_PARTIALS for token in tokens if token):
                continue
            queue.append((child, depth + 1))
    return repos


def parse_github_origin(origin_url: str) -> tuple[str, str] | None:
    owner, repo = _parse_remote(origin_url)
    if owner and repo and "github.com" in origin_url.lower():
        return owner, repo
    return None


def build_repo_project_seed(repo_path: Path) -> RepoProjectSeed | None:
    origin_url = _run_git(repo_path, "remote", "get-url", "origin")
    parsed = parse_github_origin(origin_url)
    if parsed is None:
        return None
    owner, repo = parsed
    hints = discover_git_project_hints(repo_path)
    match_terms = hints.match_terms if hints is not None else [repo.lower(), f"{owner}/{repo}".lower()]
    match_terms = [term for term in match_terms if term]
    if not match_terms:
        return None
    return RepoProjectSeed(
        repo_path=repo_path,
        name=repo,
        customer=owner,
        match_terms=match_terms,
        origin_url=origin_url,
    )


def merge_repo_project_seeds(existing_payload: dict, seeds: list[RepoProjectSeed], *, root: Path) -> tuple[dict, RepoBootstrapSummary]:
    payload = dict(existing_payload)
    projects = list(payload.get("projects", []))
    by_name = {
        str(project.get("name", "")).strip().lower(): idx
        for idx, project in enumerate(projects)
        if isinstance(project, dict) and str(project.get("name", "")).strip()
    }
    added = 0
    updated = 0
    skipped = 0
    for seed in seeds:
        idx = by_name.get(seed.name.lower())
        if idx is None:
            projects.append(
                {
                    "name": seed.name,
                    "customer": seed.customer,
                    "match_terms": list(seed.match_terms),
                    "tracked_urls": [],
                    "email": "",
                    "invoice_title": "",
                    "invoice_description": "",
                    "enabled": True,
                }
            )
            by_name[seed.name.lower()] = len(projects) - 1
            added += 1
            continue
        project = dict(projects[idx])
        changed = False
        if not str(project.get("customer", "")).strip() and seed.customer:
            project["customer"] = seed.customer
            changed = True
        existing_terms = as_list(project.get("match_terms"))
        seen_terms = {term.lower() for term in existing_terms}
        merged_terms = list(existing_terms)
        for term in seed.match_terms:
            if term.lower() not in seen_terms:
                merged_terms.append(term)
                seen_terms.add(term.lower())
        if merged_terms != existing_terms:
            project["match_terms"] = merged_terms
            changed = True
        projects[idx] = project
        if changed:
            updated += 1
        else:
            skipped += 1
    payload["projects"] = projects
    return payload, RepoBootstrapSummary(
        root=root,
        discovered=len(seeds),
        added=added,
        updated=updated,
        skipped=skipped,
    )


def assess_match_terms_coverage(cwd: Path, profiles: list[dict]) -> MatchTermsCoverage:
    hints = discover_git_project_hints(cwd)
    if hints is None:
        return MatchTermsCoverage("na", "Not inside a git repository.", [])
    if not profiles:
        return MatchTermsCoverage("warn", "No enabled project profiles found for this repo.", hints.match_terms)
    suggested = {term.lower() for term in hints.match_terms}
    for profile in profiles:
        terms = {str(term).strip().lower() for term in profile.get("match_terms", []) if str(term).strip()}
        name = str(profile.get("name", "")).strip().lower()
        if name:
            terms.add(name)
        overlap = sorted(suggested & terms)
        if overlap:
            return MatchTermsCoverage(
                "ok",
                f"Current repo cues match project `{profile.get('name', 'unknown')}` via {', '.join(overlap)}.",
                hints.match_terms,
                matched_project=str(profile.get("name", "")),
            )
    return MatchTermsCoverage(
        "warn",
        "Current repo git cues are not covered by any project's `match_terms`.",
        hints.match_terms,
    )