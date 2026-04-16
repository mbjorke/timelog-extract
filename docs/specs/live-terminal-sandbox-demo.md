# Live Terminal Sandbox Demo Spec

Status: Proposed (approved for build)  
Owner: Maintainer + active implementation agent  
Target: `gittan.sh` public website

## Problem

The current website terminal experiences have been either static or animation-driven.
They are hard to maintain, can feel visually unstable, and do not provide a true
"real terminal" interaction model.

## Goal

Ship a robust, slim, secure live terminal demo where visitors can type commands into
a terminal-like UI and receive real command output from a sandboxed runtime using
deterministic demo data.

## Non-goals

- No access to visitor local files or browser history.
- No arbitrary command execution.
- No long-lived per-user environments.
- No production report generation from real user data.

## User experience requirements

1. Visitor sees a terminal prompt and a blinking cursor.
2. Visitor can type command text and press Enter.
3. Supported commands execute and stream output line-by-line.
4. Unsupported commands fail with a clear help message.
5. Session can be reset quickly to a clean initial state.
6. Default behavior is calm: no autoplay loops and no forced movement.

## Command contract (v1 allowlist)

Allowed commands (exact or normalized aliases):

- `gittan doctor`
- `gittan report --today --source-summary`
- `gittan report --today --format json`
- `gittan report --today --invoice-pdf`
- `help`
- `clear`

Any other input returns:

- `Command not allowed in demo sandbox. Try: help`

## Implementation tracking

Build-phase checklist (P0–P5) lives in `docs/live-terminal-sandbox/README.md`.

## Architecture

### Frontend

- `xterm.js` (or equivalent) terminal component.
- WebSocket (preferred) or SSE stream for output.
- Local input normalization and command echoing.
- No autoplay execution on page load.

### Backend

- Lightweight API service with:
  - session creation endpoint
  - command execution endpoint
  - output streaming endpoint
- Per-session ephemeral sandbox runtime.

### Runtime isolation

Preferred options (in order):

1. Firecracker microVM sandbox pool.
2. Container sandbox with strong isolation (`gVisor`/`Kata`).
3. Rootless Docker + seccomp/apparmor (minimum acceptable for v1 only).

## Security requirements

Mandatory:

- strict command allowlist (server-side enforced)
- no shell passthrough
- no host filesystem mounts with secrets
- outbound network blocked by default
- CPU/memory/time limits per execution
- hard session TTL (e.g. 60-120 seconds)
- full environment reset between sessions
- server-side rate limiting and abuse throttling
- structured audit logs for executed allowlisted commands

## Data model

Demo uses deterministic fixture data only:

- versioned fixture bundle in repo (`tests/fixtures` or dedicated `demo/fixtures`)
- readonly mount inside sandbox
- pinned expected output snapshots for each allowed command

## Reliability requirements

- P95 command start latency under 1.5s (warm path).
- P95 end-to-end command completion under 4s for allowlisted commands.
- If sandbox fails, show fallback:
  - `Demo temporarily unavailable. Please try again.`
- Terminal must remain interactive even on command errors.

## Rollout plan

### Phase 1: Minimal robust release

- Terminal UI + backend allowlist + deterministic output.
- Strong calm UX (no auto replay).
- Basic monitoring and rate limit.

### Phase 2: Hardening

- Move runtime to microVM-level isolation (if Phase 1 used containers).
- Add synthetic monitoring for each demo command.
- Add per-command performance budget alerts.

## Test plan

Automated:

- unit tests for command parser/normalizer
- allowlist enforcement tests
- snapshot tests for demo outputs
- sandbox lifecycle tests (create/expire/reset)

Manual:

- type each allowlisted command in UI
- verify unknown command handling
- verify reset/clear behavior
- verify multi-session isolation in parallel browsers

Security validation:

- attempt shell escape tokens (`;`, `&&`, subshell patterns)
- attempt path traversal and env leakage
- verify outbound network is blocked in sandbox

## Operational notes

- Keep demo environment separate from production app secrets.
- Never run demo commands in the same runtime context as CI or deploy jobs.
- Prefer immutable image tags and pinned runtime versions.

## Acceptance criteria

- Visitors can type commands directly in terminal UI and see streamed output.
- Only allowlisted commands run; all other input is rejected safely.
- No autoplay/replay animation remains on page.
- Demo data is deterministic and maintained via fixtures/snapshots.
- Security controls above are implemented and verified.
