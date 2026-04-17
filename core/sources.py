"""Source-name constants and ordering for timelog processing."""

CURSOR_CHECKPOINTS_SOURCE = "Cursor checkpoints"
WORKLOG_SOURCE = "TIMELOG.md"
GITHUB_SOURCE = "GitHub"
TOGGL_SOURCE = "Toggl"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Claude.ai (web)",
    "Gemini (web)",
    "Cursor",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    "GitHub Copilot CLI",
    "Gemini CLI",
    WORKLOG_SOURCE,
    "Apple Mail",
    "Chrome",
    "Lovable (desktop)",
    GITHUB_SOURCE,
    TOGGL_SOURCE,
]

AI_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop",
    "Gemini CLI",
    "Claude.ai (web)",
    "Gemini (web)",
    "Lovable (desktop)",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    "GitHub Copilot CLI",
    WORKLOG_SOURCE,
}
