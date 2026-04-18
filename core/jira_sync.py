"""Build Jira worklog candidates from report data and git metadata."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional

from collectors.jira import JiraCredentials, post_jira_worklog

if TYPE_CHECKING:
    from core.report_service import ReportPayload

ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


@dataclass
class GitCommit:
    committed_at: datetime
    subject: str


@dataclass
class JiraWorklogCandidate:
    issue_key: str
    day: str
    started: datetime
    seconds: int
    projects: List[str]
    source: str

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0

    @property
    def comment(self) -> str:
        projects = ", ".join(sorted(self.projects))
        return f"Gittan sync ({self.day}) project(s): {projects}"


@dataclass
class JiraSyncSummary:
    posted: int = 0
    skipped: int = 0
    unresolved: int = 0
    failed: int = 0


def extract_issue_key(text: str) -> Optional[str]:
    match = ISSUE_KEY_RE.search(text or "")
    if not match:
        return None
    return match.group(1)


def _git_lines(repo_path: Path, *args: str) -> List[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def load_current_branch_issue_key(repo_path: Path) -> Optional[str]:
    lines = _git_lines(repo_path, "branch", "--show-current")
    if not lines:
        return None
    return extract_issue_key(lines[0].strip())


def load_commit_tags(repo_path: Path, dt_from: datetime, dt_to: datetime) -> List[GitCommit]:
    since = (dt_from - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    until = (dt_to + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _git_lines(
        repo_path,
        "log",
        f"--since={since}",
        f"--until={until}",
        "--pretty=format:%ct\t%s",
    )
    commits: List[GitCommit] = []
    for row in rows:
        try:
            epoch_s, subject = row.split("\t", 1)
            ts = datetime.fromtimestamp(int(epoch_s), tz=timezone.utc).astimezone()
        except (ValueError, OSError):
            continue
        commits.append(GitCommit(committed_at=ts, subject=subject))
    return commits


def _issue_key_for_session(
    start: datetime,
    end: datetime,
    commits: Iterable[GitCommit],
    branch_key: Optional[str],
) -> tuple[Optional[str], str]:
    session_keys: List[str] = []
    for commit in commits:
        if start <= commit.committed_at <= end:
            key = extract_issue_key(commit.subject)
            if key:
                session_keys.append(key)
    if session_keys:
        return session_keys[0], "commit"
    if branch_key:
        return branch_key, "branch"
    return None, "unresolved"


def build_jira_worklog_candidates(
    report: ReportPayload,
    repo_path: Path,
) -> tuple[List[JiraWorklogCandidate], int]:
    commits = load_commit_tags(repo_path, report.dt_from, report.dt_to)
    branch_key = load_current_branch_issue_key(repo_path)
    unresolved_sessions = 0
    buckets: dict[tuple[str, str], JiraWorklogCandidate] = {}

    for day, day_data in report.overall_days.items():
        sessions = day_data.get("sessions", [])
        for start, end, session_events in sessions:
            issue_key, source = _issue_key_for_session(start, end, commits, branch_key)
            if not issue_key:
                unresolved_sessions += 1
                continue
            seconds = int(round(max(0.0, report.args.min_session / 60) * 3600))
            try:
                from core.domain import session_duration_hours
                from core.sources import AI_SOURCES

                seconds = int(
                    round(
                        session_duration_hours(
                            session_events,
                            start,
                            end,
                            report.args.min_session,
                            report.args.min_session_passive,
                            AI_SOURCES,
                        )
                        * 3600
                    )
                )
            except Exception as exc:
                import logging
                logging.warning(f"Failed to compute session duration, using fallback: {exc}")
            key = (issue_key, day)
            projects = sorted({str(evt.get("project") or "Uncategorized") for evt in session_events})
            if key not in buckets:
                buckets[key] = JiraWorklogCandidate(
                    issue_key=issue_key,
                    day=day,
                    started=start,
                    seconds=max(0, seconds),
                    projects=projects,
                    source=source,
                )
            else:
                buckets[key].seconds += max(0, seconds)
                buckets[key].projects = sorted(set(buckets[key].projects) | set(projects))

    candidates = sorted(buckets.values(), key=lambda item: (item.day, item.issue_key))
    return candidates, unresolved_sessions


def post_candidate(creds: JiraCredentials, candidate: JiraWorklogCandidate) -> str:
    return post_jira_worklog(
        creds=creds,
        issue_key=candidate.issue_key,
        started=candidate.started,
        time_spent_seconds=candidate.seconds,
        comment=candidate.comment,
    )
