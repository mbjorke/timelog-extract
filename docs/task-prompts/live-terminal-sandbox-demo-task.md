# Task Prompt: Live Terminal Sandbox Demo

Use this prompt to build a production-grade interactive terminal demo on
`gittan.sh` backed by a secure sandbox, following the approved spec.

## Goal

Ship a real interactive terminal experience (typed commands + streamed output)
without exposing host systems, secrets, or arbitrary execution risk.

## Priority

This task is priority #2 (after inline CLI UX validation).

## Source of truth

- `docs/specs/live-terminal-sandbox-demo.md`
- `docs/PRIVACY_SECURITY.md`
- `docs/CI.md`

## Scope (v1)

1. Frontend terminal UI (xterm.js or equivalent):
   - visible prompt + cursor
   - typed input + Enter submit
   - streamed output
2. Backend demo execution API:
   - create/reset session
   - run allowlisted command
   - stream output
3. Sandboxed command execution:
   - strict allowlist enforcement server-side
   - deterministic demo fixture data only
4. Calm UX:
   - no autoplay replay loops
   - clear error messages and reset behavior

## Command allowlist (initial)

- `gittan doctor`
- `gittan report --today --source-summary`
- `gittan report --today --format json`
- `gittan report --today --invoice-pdf`
- `help`
- `clear`

All non-allowlisted input must be rejected safely.

## Security requirements (mandatory)

- no shell passthrough
- no arbitrary command execution
- no secret-bearing filesystem mounts
- outbound network blocked by default for sandbox runtime
- CPU/memory/time limits per run
- short session TTL and hard cleanup
- rate limiting + abuse guard

## Suggested delivery slicing

### Task-A (minimum secure path)

- Implement terminal UI + backend allowlist + deterministic fixture outputs.
- Add server tests for command validation and rejection paths.

### Task-B (hardening)

- Strengthen isolation layer (container hardening/microVM path).
- Add monitoring and operational alerts for failures/timeouts.

## Tests (required)

- unit tests for parser/allowlist validation
- integration tests for command round-trip (request → output stream)
- snapshot tests for deterministic demo output
- negative tests for blocked command patterns (`;`, `&&`, subshell, traversal)
- run `./scripts/run_autotests.sh`

## Acceptance criteria

- User can type supported commands in site terminal and get streamed output.
- Unsupported commands are blocked with clear message.
- Runtime uses deterministic fixture data and cannot access local user data.
- Security controls above are implemented and verified.
- Site remains stable/readable without motion-heavy behavior.

## Task output format

When done, provide:

1. Architecture summary (frontend, API, sandbox layer)
2. Security control checklist with evidence
3. Demo command transcripts (happy path + blocked path)
4. Test evidence and remaining risks
