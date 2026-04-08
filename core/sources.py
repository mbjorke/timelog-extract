"""Source-name constants and ordering for timelog processing."""

CURSOR_CHECKPOINTS_SOURCE = "Cursor checkpoints"
WORKLOG_SOURCE = "TIMELOG.md"

SOURCE_ORDER = [
    "Claude Code CLI",
    "Claude Desktop",
    "Claude.ai (web)",
    "Gemini (web)",
    "Cursor",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    "Gemini CLI",
    WORKLOG_SOURCE,
    "Apple Mail",
    "Chrome",
]

AI_SOURCES = {
    "Claude Code CLI",
    "Claude Desktop",
    "Gemini CLI",
    "Claude.ai (web)",
    "Gemini (web)",
    CURSOR_CHECKPOINTS_SOURCE,
    "Codex IDE",
    WORKLOG_SOURCE,
}
