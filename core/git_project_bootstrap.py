"""Git-aware project bootstrap and coverage checks for local onboarding."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


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


def _run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
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
