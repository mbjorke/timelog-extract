# V1 Scope Decision

## Product Shape

- Delivery target: Cursor Marketplace plugin (GUI-first), backed by local Python engine.
- Processing mode: local-only for v1 (no cloud upload path).

## Supported OS (v1)

- Primary support: macOS.
- Linux/Windows: graceful unsupported-source behavior only, no parity promise in v1.

## Sources Included in v1

- Claude Code CLI logs
- Claude Desktop sessions
- Claude.ai tracked URLs
- Gemini tracked URLs + Gemini CLI sessions
- Cursor logs + Cursor checkpoints
- Codex IDE index
- Project worklog (`TIMELOG.md`)

## Sources Deferred

- Apple Mail and Screen Time as default-enabled sources are deferred behind explicit opt-in.
- Full Briox invoice push flow deferred to v1.1+ (keep read/test integration outside core plugin path).

## v1 UX Commitments

- Setup wizard
- Data-source consent screen
- Source toggles
- Run report action
- Results summary view
- Export/open PDF actions
