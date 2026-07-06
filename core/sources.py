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
    "Windsurf",
    "Codex IDE",
    "Conductor",
    "GitHub Copilot CLI",
    "Gemini CLI",
    "Zed",
    WORKLOG_SOURCE,
    "Apple Mail",
    "Chrome",
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
    "Windsurf": DIRECT_WORK_EVIDENCE,
    "Codex IDE": DIRECT_WORK_EVIDENCE,
    "Conductor": DIRECT_WORK_EVIDENCE,
    "GitHub Copilot CLI": DIRECT_WORK_EVIDENCE,
    "Zed": DIRECT_WORK_EVIDENCE,
    GITHUB_SOURCE: DELIVERY_EVIDENCE,
    GIT_COMMITS_SOURCE: DELIVERY_EVIDENCE,
    JIRA_SOURCE: DELIVERY_EVIDENCE,
    # Policy groups Chrome and Lovable-desktop history as passive context:
    # good for project hints, noisy as duration proof on their own.
    "Chrome": PASSIVE_CONTEXT,
    "Lovable (desktop)": PASSIVE_CONTEXT,
    "Apple Mail": PASSIVE_CONTEXT,
    CALENDAR_SOURCE: SCHEDULED_CONTEXT,
    "Screen Time": COVERAGE_COMPARATOR,
    # Opt-in presence buffer (read-only, timestamps only); see
    # core/timely_memory.py. Comparator context, never billable input.
    "Timely Memory": COVERAGE_COMPARATOR,
}


def get_source_role(source_name: str) -> str:
    """Evidence role for a source name; unknown sources default to passive context."""
    return SOURCE_ROLES.get(str(source_name or ""), PASSIVE_CONTEXT)


PASSIVE_DURATION_SOURCES = frozenset(
    name for name, role in SOURCE_ROLES.items() if role == PASSIVE_CONTEXT
)

# Attendance categories per GH-284.
# Attended: user is present (IDE focus, browser, manual logs, meetings).
# Agent: autonomous work (GitHub merges, AI CLI loops, agent-mode IDE turns).
ATTENDED_SOURCES = {
    "Cursor",
    "Antigravity",
    "Windsurf",
    "Codex IDE",
    "Zed",
    "Chrome",
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
    "Lovable (desktop)",
    CURSOR_CHECKPOINTS_SOURCE,
}
