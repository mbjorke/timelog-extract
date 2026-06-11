# Conversational UI and the modal wall — stack direction

Status: exploratory (planning session 2026-06; not final policy)

## The reframe

The primary UX for Gittan's GUI era is **a conversation, not a dashboard**:

> "Hey gittan, what did I work on today?"

The AI's job is narrow and specific: **suggest optimal configuration from
natural language, orchestrate existing CLI commands, and reformat output
for the user's need** (summary, invoice text, sync payload). It is *not* a
classification engine — the CLI already produces 50%+ of suggestions
deterministically (`projects-audit`, `review --json`, rule suggestions).

A dashboard view is just what the assistant renders when the answer calls
for it.

## Why no MCP (theoretically)

The CLI **is** the API. `gittan report --format json`, `gittan review
--json`, `gittan projects-trim -i removals.json` are structured,
documented contracts. An AI runtime with terminal execution plus a skill
document describing the commands needs no protocol layer. MCP can be
revisited if a concrete consumer demands it; nothing in this direction
requires it.

## The modal wall

The boundary between terminal UI and web UI is not a feature decision —
it is a **decision-weight threshold**:

| Decision weight | Surface | Example |
| --- | --- | --- |
| Low (confirm y/n) | plain CLI / questionary | "Apply trim? y/n" |
| Medium (review a few items in place) | React Ink TUI overlay | accept/edit/skip rule proposals with visible context |
| High (dense context needed to decide) | web view | triage: assign project to weak-signal events with session context, sortable tables |

Modal dialogs were historically the hard part in the CLI: sequential,
blocking, context scrolls away. React Ink overlays solve the medium tier;
the web view exists precisely for the moment an overlay is not enough.

## Stack direction (to validate before building)

- **DB:** SQLite in `~/.gittan/` for state files can't hold well — triage
  decisions, intent capture index, sync history. Python stdlib, single
  user-owned file, syncs as data (fits `decisions/private-not-local.md`).
- **TUI:** React Ink-style terminal UI (tables, markdown, overlays,
  streaming) — proven by Hermes Agent's CLI (see
  `ideas/hermes-agent-distribution.md`).
- **Web view:** React/TypeScript, shared design language with the Cursor
  extension; opened *by* the conversation for high-weight decisions, not
  navigated to as a standalone product.
- **Mobile:** deferred. Messaging-gateway agents (Telegram/Signal via a
  self-hosted agent runtime) are the stopgap for remote intent capture.

## What this retires

- The "Freelance Bridge" SaaS-middleware dashboard prototype as a product
  shape. Its visual language can be reused for the web view; its hosted
  premise conflicts with private-first. Execution log and next slices for the
  replacement work live in `freelance-bridge-planning-arc.md`.
- Accounting-connector-first sequencing. Sync targets (Toggl first, Briox
  later) are downstream consumers of the review loop, and the review loop
  depends on intent capture (`specs/intent-capture.md`).

## Open questions

- Does the Cursor extension webview and the standalone web view share one
  component library, or is the extension allowed to lag?
- `gittan chat` as a CLI entry to the conversational layer: thin wrapper
  around a user-configured provider, or leave conversation entirely to
  external agent runtimes?
