# Hermes Agent — integration pattern and distribution channel

Status: exploratory (planning session 2026-06; not final policy)

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous
Research, MIT) is a self-hosted agent runtime: persistent memory,
autonomous skill creation (agentskills.io standard, `~/.hermes/skills/`),
terminal execution, multi-platform messaging gateway (Telegram, Discord,
Slack, Signal, WhatsApp, …), React Ink TUI, Python JSON-RPC backend.

Treat it as **an example/experiment of the agent-runtime class**, not a
hard dependency. Whatever holds for Hermes should hold for any agent with
terminal execution + a skills standard.

## Why it matters to Gittan

1. **Integration costs ~nothing.** An agent with terminal execution
   consumes the existing CLI contracts directly (`report --format json`,
   `review --json`, `projects-trim`). No MCP server, no new API surface
   (see `ideas/conversational-ui-stack.md`).
2. **The gateway is the free mobile story.** "Tag this thread → project X"
   from Telegram/Signal writes an intent record
   (`specs/intent-capture.md`) with zero custom mobile code.
3. **Self-hosted matches private-first.** No telemetry, user-operated —
   compatible with `decisions/private-not-local.md`.
4. **Skills are the learning loop.** An agent skill that improves with
   use is the "AI layer for consistent improvement" without building one
   inside Gittan.

## Distribution / marketing angle

A first-class, actively maintained `gittan` skill in the agentskills.io
ecosystem puts Gittan in front of exactly the right audience: developers
already working AI-natively, who have the activity worth tracking. An
active skill (or a visible integration branch) is better marketing than
launch posts.

Candidate first deliverable: a skill document that teaches an agent the
CLI contract — which commands answer "what did I work on today?", which
are read-only vs write-path, and the confirm-before-write rules.

## Guardrail (decide before building)

Write-path commands (`projects-trim`, future `triage-apply`, any sync
push) must keep an explicit human confirmation step even when invoked by
an agent. Read-only JSON commands are safe for autonomous use; writes are
not. The skill document must encode this split, and the CLI should keep
offering `--dry-run` everywhere a write exists.

## Open questions

- Does an agent-authored config edit go through a diff-preview the human
  approves in chat, or must it route to the CLI confirm flow?
- Pin the skill to CLI version ranges? (JSON schema versions already exist
  for some commands; the skill should declare what it was written against.)
- Which marketplace is primary for discovery: agentskills.io, Claude
  integrations, or Cursor Marketplace? (All three eventually; effort order
  matters.)
