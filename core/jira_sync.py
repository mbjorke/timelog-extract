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
    def marker(self) -> str:
        """Stable idempotency token embedded in the worklog comment.

        Jira worklogs do not support tags, so re-run detection relies on this
        deterministic per-issue/per-day token appearing in an existing comment.
        """
        return f"[gittan:{self.issue_key}:{self.day}]"

    @property
    def comment(self) -> str:
        projects = ", ".join(sorted(self.projects))
        return f"Gittan sync ({self.day}) project(s): {projects} {self.marker}"


@dataclass
class JiraSyncSummary:
    posted: int = 0
    already: int = 0
    not_found: int = 0
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
    """
    Collects git commits for the given time window and returns them as GitCommit objects.
    
    Searches the repository at `repo_path` for commits whose commit timestamps fall within
    the interval from `dt_from` to `dt_to` extended by two days on each side. Each returned
    GitCommit has `committed_at` converted to the local timezone and `subject` taken from
    the commit message. Malformed or unparsable git log lines are skipped.
    
    Parameters:
        repo_path (Path): Filesystem path of the git repository.
        dt_from (datetime): Start of the target interval (inclusive before extension).
        dt_to (datetime): End of the target interval (inclusive before extension).
    
    Returns:
        List[GitCommit]: Commits whose commit times fall in the expanded interval, ordered
        as returned by git log (most recent first by default).
    """
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
    """
    Selects the Jira issue key for a work session from commit subjects or the current branch.
    
    Searches commits whose commit timestamp falls between `start` and `end` for a Jira-like issue key; if any are found returns the first match with source `"commit"`. If no commit key is found and `branch_key` is provided, returns the branch key with source `"branch"`. If neither yields a key, returns `None` with source `"unresolved"`.
    
    Returns:
        tuple[Optional[str], str]: `(issue_key, source)` where `issue_key` is the chosen issue key or `None`, and `source` is one of `"commit"`, `"branch"`, or `"unresolved"`. If `source` is `"commit"`, `issue_key` is the first matching key found in commits within the session interval.
    """
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


def build_issue_key_map(profiles: Optional[List[dict]]) -> dict[str, str]:
    """Map project name -> explicit ``jira_issue_key`` for profiles that declare one."""
    mapping: dict[str, str] = {}
    for profile in profiles or []:
        name = str(profile.get("name") or "").strip()
        key = str(profile.get("jira_issue_key") or "").strip()
        if name and key:
            mapping[name] = key
    return mapping


def _candidates_from_reported(
    reported: dict[tuple[str, str, Optional[str]], float],
    issue_keys: dict[str, str],
) -> tuple[List[JiraWorklogCandidate], int]:
    """Reported-mode (Phase 3b): build worklog candidates from confirmed reported
    hours per ``(project, day, issue_key)``. Each record's own ``issue_key`` (git-
    inferred at observation, or a manual ``--issue``) wins; when it is ``None`` the
    project's profile ``jira_issue_key`` is the fallback. Records that resolve to no
    issue are counted unresolved (never posted)."""
    from core.reported_sync import day_start

    unresolved = 0
    buckets: dict[tuple[str, str], JiraWorklogCandidate] = {}
    for (project, day, record_issue), hours in sorted(reported.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2] or "")):
        issue_key = record_issue or issue_keys.get(project)
        if not issue_key:
            unresolved += 1
            continue
        seconds = int(round(max(0.0, hours) * 3600))
        if seconds <= 0:
            continue
        key = (issue_key, day)
        if key not in buckets:
            buckets[key] = JiraWorklogCandidate(
                issue_key=issue_key,
                day=day,
                started=day_start(day),
                seconds=seconds,
                projects=[project],
                source="reported",
            )
        else:
            buckets[key].seconds += seconds
            buckets[key].projects = sorted(set(buckets[key].projects) | {project})
    candidates = sorted(buckets.values(), key=lambda item: (item.day, item.issue_key))
    return candidates, unresolved


def build_jira_worklog_candidates(
    report: ReportPayload,
    repo_path: Path,
    profiles: Optional[List[dict]] = None,
    home: Optional[Path] = None,
) -> tuple[List[JiraWorklogCandidate], int]:
    """
    Aggregate report sessions into JiraWorklogCandidate objects by inferring Jira issue keys from git commits or the current branch and summing per-issue/per-day durations.
    
    Parameters:
        report (ReportPayload): Report data containing `overall_days` mapping of days to session lists, `dt_from`/`dt_to` window, and `args` with `min_session` and `min_session_passive` used to compute session durations.
        repo_path (Path): Path to the local git repository used to load commits and the current branch for issue-key inference.
    
    Returns:
        tuple[List[JiraWorklogCandidate], int]: A tuple where the first element is a list of aggregated worklog candidates (one per issue key per day, sorted by day then issue key) and the second element is the count of sessions for which no issue key could be resolved.

    When confirmed/edited reported_time exists for the report window, candidates are
    built from those confirmed hours per ``(project, day, issue_key)`` — each
    record's git-inferred/manual ``issue_key`` wins, falling back to the project's
    profile ``jira_issue_key`` (Phase 3b reported-mode); otherwise issue keys are
    inferred from git as before (the pre-adoption fallback).
    """
    from core.reported_sync import reported_issue_hours_for_window

    reported = reported_issue_hours_for_window(report, home)
    if reported is not None:
        return _candidates_from_reported(reported, build_issue_key_map(profiles))

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


def candidate_already_posted(
    candidate: JiraWorklogCandidate,
    existing_worklogs: Iterable[dict],
) -> bool:
    """Return True if an existing worklog already carries this candidate's marker.

    Worklog comments are ADF docs (or, defensively, strings/None); the plain text
    is extracted and matched against the candidate's deterministic marker so
    re-running `gittan jira-sync` skips already-posted issue/day buckets.
    """
    from collectors.jira import adf_comment_text

    marker = candidate.marker
    for worklog in existing_worklogs:
        if not isinstance(worklog, dict):
            continue
        if marker in adf_comment_text(worklog.get("comment")):
            return True
    return False


def post_candidate(creds: JiraCredentials, candidate: JiraWorklogCandidate) -> str:
    return post_jira_worklog(
        creds=creds,
        issue_key=candidate.issue_key,
        started=candidate.started,
        time_spent_seconds=candidate.seconds,
        comment=candidate.comment,
    )
