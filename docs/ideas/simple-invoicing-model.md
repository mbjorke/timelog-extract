# Simple Invoicing Model (solo-first)

Status: Working model for near-term product decisions. Keep this aligned with
`docs/security/privacy-security.md` and shipped CLI behavior.

## Why this model

For a solo developer/business, the safest path is to avoid a broad inbound API.
Instead, keep Gittan as a local source-of-truth and use explicit exports plus
optional push connectors.

This reduces:

- security complexity (auth, scope design, token management),
- accidental data leakage,
- maintenance burden for a small team.

## Core principles

1. Local-first by default: no always-on remote service required.
2. User-triggered actions only: export/push happens when the user runs a command.
3. Minimum necessary data: send summaries, not raw traces, unless explicitly needed.
4. Reversible workflows: draft-first pushes and clear rollback paths.

## Recommended integration pattern

### 1) Export, do not expose

- Keep primary workflow as CLI generation of local artifacts:
  - JSON (`--format json`)
  - HTML (`--report-html`)
  - Invoice PDF (`--invoice-pdf`)
- Treat these artifacts as reviewable handoff files.

### 2) Push-only connectors

- For external systems (for example accounting/time systems), prefer a push flow:
  - prepare payload locally,
  - preview/dry-run,
  - explicit confirm,
  - push once.
- Avoid full bi-directional sync in early versions.

### 3) Draft-first writes

- If the target system supports draft state, create draft records first.
- Never auto-finalize/send invoices as part of first iteration.

## Guardrails for safe pushes

- Dry-run mode prints exact outgoing payload before network calls.
- Two-step command flow: `prepare` then `push`.
- Idempotency keys prevent duplicate submissions on retries.
- Local operation log stores:
  - operation ID,
  - timestamp,
  - target system identifiers,
  - payload hash.
- Rollback command should exist where API supports reversing draft actions.
- If rollback is not possible via API, print clear manual recovery steps.

## Lovable as delivery layer

Gittan can stay local-first while Lovable acts as an optional SaaS layer for
presentation and sending.

Recommended high-level sequence:

1. Gittan prepares local invoice artifacts and a reviewable export payload.
2. User reviews and explicitly approves upload.
3. Lovable receives only approved data categories and creates a draft invoice.
4. User edits design/recipient details in Lovable and confirms send separately.

Control model:

- Data leaves local environment only after explicit user action.
- Import must create draft state by default, not auto-send.
- First upload should include a consent screen describing destination and data
categories.
- Users must be able to delete drafts and revoke future uploads.
- Regret handling should include operation IDs and manual undo instructions when
target APIs do not support full rollback.

## Regret recovery model

When a user says "I regret this push", the system should support:

1. identifying the exact operation from local logs,
2. attempting automated rollback for reversible states,
3. falling back to clear manual undo guidance with IDs and timestamps.

## Scope boundaries (for now)

In scope:

- improve local outputs (JSON/HTML/PDF),
- simplify "approve then push" connector UX,
- document safe defaults clearly.

Out of scope:

- generic public API surface for arbitrary queries,
- full sync engines with remote systems,
- complex multi-tenant auth models.

## Relation to existing repo capabilities

- Engine API boundary exists for local callers in `core/engine_api.py`.
- CLI already supports PDF/JSON/HTML output in `core/report_cli.py`.
- Briox experimentation exists as standalone connection test script
(`briox_connection_test.py`) and can evolve into draft-first push flows.

## Product framing

Short version: "Export and push with confirmation" is the default business model.
It is safer, simpler, and better aligned with solo-founder constraints than
launching a broad API too early.