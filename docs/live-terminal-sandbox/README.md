# Live terminal sandbox (implementation spine)

Companion to `docs/specs/live-terminal-sandbox-demo.md`. Use this folder for **build tracking** so the high-risk site work stays traceable without blocking CLI releases.

## Phase checklist

- [x] **P0 — Contract:** allowlisted commands frozen; error copy for unknown input (spec § Command contract). Implemented in `core/live_terminal/contract.py` (import from server-side demo code; do not duplicate lists).
- [x] **P1 — Backend sketch:** session create + execute + stream; **no** shell passthrough; server-side allowlist only. Implemented: `core/live_terminal/http.py` + `core/live_terminal/service.py` (stub output via `core/live_terminal/stub_output.py`); run `python3 scripts/live_terminal_demo_server.py`. Responses are full body (streaming/WebSocket deferred to P3).
- [ ] **P2 — Isolation pick:** document chosen option (Firecracker / gVisor / rootless Docker) and threat model one-pager.
- [ ] **P3 — Frontend:** xterm.js (or equivalent), WebSocket or SSE, no autoplay on load.
- [ ] **P4 — Fixture data:** deterministic demo workspace; reset path tested under load.
- [ ] **P5 — Ops:** rate limits, logging redaction, CI job for static + API split if applicable.

## Notes

- Production report generation from visitor machines remains a **non-goal** (spec).
- Keep demo traffic separate from PyPI install analytics; document host boundary in `docs/ci.md` when wiring deploy.
