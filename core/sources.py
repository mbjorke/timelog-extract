"""Source-name constants and ordering for timelog processing."""

CURSOR_CHECKPOINTS_SOURCE = "Cursor checkpoints"
WORKLOG_SOURCE = "TIMELOG.md"
GITHUB_SOURCE = "GitHub"
TOGGL_SOURCE = "Toggl"
JIRA_SOURCE = "Jira"
CALENDAR_SOURCE = "Calendar"
GIT_COMMITS_SOURCE = "Git commits"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Claude Desktop (Code)",
    "Claude.ai (web)",
    "Gemini (web)",
    "Cursor",
    "Cursor (agent)",
    CURSOR_CHECKPOINTS_SOURCE,
    "Antigravity",
    "Devin Desktop",
    "VS Code",
    "Codex IDE",
    "Conductor",
    "GitHub Copilot CLI",
    "Gemini CLI",
    "Zed",
    WORKLOG_SOURCE,
    "Apple Mail",
    "Chrome",
    "WordPress",
    "Lovable (web)",
    "Lovable (desktop)",
    GITHUB_SOURCE,
    GIT_COMMITS_SOURCE,
    TOGGL_SOURCE,
    CALENDAR_SOURCE,
]

AI_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop",
    "Claude Desktop (Code)",
    "Gemini CLI",
    "Lovable (desktop)",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    "Conductor",
    "Cursor (agent)",
    "GitHub Copilot CLI",
    "Zed",
    WORKLOG_SOURCE,
}

# Evidence roles per docs/specs/source-evidence-policy.md. A source can be good
# evidence for context without being strong evidence for worked time or invoice
# approval. These roles travel with each evidence record (see
# docs/specs/local-evidence-shadow-log.md) so the durable store keeps the
# observed/classified/approved layers separable.
PRIMARY_CLAIM = "primary_claim"
DIRECT_WORK_EVIDENCE = "direct_work_evidence"
DELIVERY_EVIDENCE = "delivery_evidence"
PASSIVE_CONTEXT = "passive_context"
SCHEDULED_CONTEXT = "scheduled_context"
COVERAGE_COMPARATOR = "coverage_comparator"

SOURCE_ROLES = {
    WORKLOG_SOURCE: PRIMARY_CLAIM,
    TOGGL_SOURCE: PRIMARY_CLAIM,
    "Claude Code CLI": DIRECT_WORK_EVIDENCE,
    "Claude Desktop": DIRECT_WORK_EVIDENCE,
    "Claude Desktop (Code)": DIRECT_WORK_EVIDENCE,
    "Claude.ai (web)": PASSIVE_CONTEXT,
    "Gemini (web)": PASSIVE_CONTEXT,
    "Gemini CLI": DIRECT_WORK_EVIDENCE,
    "Cursor": DIRECT_WORK_EVIDENCE,
    "Cursor (agent)": DIRECT_WORK_EVIDENCE,
    CURSOR_CHECKPOINTS_SOURCE: DIRECT_WORK_EVIDENCE,
    "Antigravity": DIRECT_WORK_EVIDENCE,
    "Devin Desktop": DIRECT_WORK_EVIDENCE,
    "VS Code": DIRECT_WORK_EVIDENCE,
    "Codex IDE": DIRECT_WORK_EVIDENCE,
    "Conductor": DIRECT_WORK_EVIDENCE,
    "GitHub Copilot CLI": DIRECT_WORK_EVIDENCE,
    "Zed": DIRECT_WORK_EVIDENCE,
    GITHUB_SOURCE: DELIVERY_EVIDENCE,
    GIT_COMMITS_SOURCE: DELIVERY_EVIDENCE,
    JIRA_SOURCE: DELIVERY_EVIDENCE,
    # Policy groups Chrome and Lovable history as passive context:
    # good for project hints, noisy as duration proof on their own.
    # WordPress / Lovable (web) are derived from Chrome; still passive_context,
    # but project_hours may give them span-capable weight.
    "Chrome": PASSIVE_CONTEXT,
    "WordPress": PASSIVE_CONTEXT,
    "Lovable (web)": PASSIVE_CONTEXT,
    "Lovable (desktop)": PASSIVE_CONTEXT,
    "Apple Mail": PASSIVE_CONTEXT,
    CALENDAR_SOURCE: SCHEDULED_CONTEXT,
    "Screen Time": COVERAGE_COMPARATOR,
    # Opt-in presence buffer (read-only, timestamps only); see
    # core/timely_memory.py. Comparator context, never billable input.
    "Timely Memory": COVERAGE_COMPARATOR,
}

# Legacy display names that must keep the same role / attendance semantics as
# their canonical successors (shadow-log replay, older doctor rows).
SOURCE_ALIASES = {
    "Windsurf": "Devin Desktop",
    "git-commit": "Git commits",
}


def canonical_source_name(source_name: str) -> str:
    """Map legacy source labels to the current canonical display name."""
    name = str(source_name or "")
    return SOURCE_ALIASES.get(name, name)


def get_source_role(source_name: str) -> str:
    """Evidence role for a source name; unknown sources default to passive context."""
    return SOURCE_ROLES.get(canonical_source_name(source_name), PASSIVE_CONTEXT)


PASSIVE_DURATION_SOURCES = frozenset(
    name for name, role in SOURCE_ROLES.items() if role == PASSIVE_CONTEXT
)

# Attendance categories per GH-284.
# Attended: user is present (IDE focus, browser, manual logs, meetings).
# Agent: autonomous work (GitHub merges, AI CLI loops, agent-mode IDE turns).
ATTENDED_SOURCES = {
    "Cursor",
    "Antigravity",
    "Devin Desktop",
    "VS Code",
    "Codex IDE",
    "Zed",
    # Lovable (desktop) is an interactive AI builder — actively building in it is
    # attended work, same tier as Cursor/Claude Desktop (GH-313, not a cloud agent).
    "Lovable (desktop)",
    # Lovable (web) is the same product in Chrome (lovable.dev / *.lovableproject.com).
    "Lovable (web)",
    "Chrome",
    "WordPress",
    "Apple Mail",
    "Claude.ai (web)",
    "Gemini (web)",
    "Claude Desktop",
    WORKLOG_SOURCE,
    TOGGL_SOURCE,
    CALENDAR_SOURCE,
    "Screen Time",
    "Timely Memory",
}

AGENT_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop (Code)",
    "GitHub",
    GIT_COMMITS_SOURCE,
    JIRA_SOURCE,
    "Cursor (agent)",
    "GitHub Copilot CLI",
    "Gemini CLI",
    "Conductor",
    CURSOR_CHECKPOINTS_SOURCE,
}

# Billable-signal axis (GH-327), orthogonal to attendance (GH-284).
# Presence-signal sources can be ATTENDED for reporting honesty, but their
# evidence is ambient presence (cache-mtime, coverage comparators) — not active
# authorship. Default billable excludes them unless --include-presence-billable
# (mirrors agent gating).
#
# Slice 1 scope (issue examples): Lovable cache-mtime + coverage comparators.
# Chrome / WordPress / Mail stay default-billable for now — they are
# passive_context on the evidence-role axis but are the primary claim for many
# client days; weighted split inside mixed sessions is Slice 2.
PRESENCE_SIGNAL_SOURCES = frozenset(
    {
        "Lovable (desktop)",  # Chromium cache-mtime on the operator's machine
        "Lovable (web)",  # same product via Chrome history
        "Screen Time",  # coverage comparator; rarely a session event
        "Timely Memory",  # coverage comparator / bracketing input
    }
)


def is_presence_signal_source(source_name: str) -> bool:
    """True when the source's evidence is presence, not authorship (GH-327)."""
    return str(source_name or "") in PRESENCE_SIGNAL_SOURCES


def session_is_presence_signal_only(events: list) -> bool:
    """True when every event source is a presence signal (or the session is empty).

    Empty sessions are treated as presence-only so bracket-only extensions stay
    confirm-gated. Mixed authorship + presence sessions return False (Slice 1:
    authorship present → whole session stays default-billable except brackets).
    """
    sources = {str(event.get("source") or "") for event in (events or [])}
    sources.discard("")
    if not sources:
        return True
    return sources <= PRESENCE_SIGNAL_SOURCES


def session_project_labels(events: list) -> list[str]:
    """Order projects for mixed-session titles: authorship before presence-only.

    A single Lovable (desktop) presence row must not lead the label when the
    session is overwhelmingly Cursor/Chrome/Worklog on other projects (GH-448).
    """
    authorship: dict[str, int] = {}
    presence: dict[str, int] = {}
    for event in events or []:
        project = str(event.get("project") or "").strip() or "Uncategorized"
        if is_presence_signal_source(str(event.get("source") or "")):
            presence[project] = presence.get(project, 0) + 1
        else:
            authorship[project] = authorship.get(project, 0) + 1
    auth_ordered = sorted(authorship.keys(), key=lambda name: (-authorship[name], name.lower()))
    presence_only = sorted(
        (name for name in presence if name not in authorship),
        key=lambda name: (-presence[name], name.lower()),
    )
    return auth_ordered + presence_only
