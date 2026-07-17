# External API integrations — current state & SaaS-facing roadmap

Status: descriptive inventory (2026-07-17) + high-level roadmap. The product
model behind every integration is the **solo-first pattern** in
[`../ideas/simple-invoicing-model.md`](../ideas/simple-invoicing-model.md):
*export, don't expose; push-only connectors; dry-run prints the exact payload;
explicit confirm; idempotency markers; draft-first; local-first always.*

This doc answers two questions:

1. **What have we already built against external APIs?** (Toggl, Jira, GitHub,
   Briox, …)
2. **What carries over into a future SaaS/hosted interface, and in what order?**

---

## 1. Integration inventory

### Overview

| Integration | Direction | Auth | Status | CLI surface |
| --- | --- | --- | --- | --- |
| **Toggl** (Track v9) | push (time entries) + read (dedup window) | API token, Basic auth | **shipped** (#175/#178/#179/#194); op-log slice is `now` (#265) | `gittan toggl-sync` |
| **Jira** (Cloud REST v3) | push (worklogs) + read (dedup, verify) | email + API token, Basic auth | **shipped** | `gittan jira-sync` |
| **GitHub** (REST) | read-only (public events → evidence) | optional token; GHE via `api/v3` base | **shipped** (collector) | source in `gittan report` |
| **Briox** (invoicing) | none — manual handoff | n/a | **not built**; deliverable is email text + Briox line via the personal `/gittan-invoice` skill | none |
| Toggl *pull* (import time) | read | — | **placeholder only**, deliberately unbuilt (push-only principle) | none |
| Calendar (macOS), Timely Memory, Lovable, WordPress, Claude.ai, … | local evidence collectors | n/a | shipped, but **not external APIs** — they read local files/DBs | sources in `gittan report` |

### Toggl — `gittan toggl-sync`

The reference implementation of the push-connector pattern.

- **Endpoints:** `POST /api/v9/workspaces/{id}/time_entries` (post),
  `GET /api/v9/me/time_entries` (dedup window), `GET /api/v9/me` (credential
  verify during onboarding). Base: `https://api.track.toggl.com`.
- **Aggregation:** one candidate per **project + day**
  (`core/toggl_sync.py::build_toggl_entry_candidates`); durations from the same
  session math as reports. Projects map via `toggl_project_id` in
  `timelog_projects.json`; unmapped projects are surfaced, never posted.
- **Guardrails:** `--dry-run` prints the exact outgoing payload; interactive
  confirm gate per post; idempotency via marker tags
  `gittan` + `gittan:{project_id}:{day}` — re-runs list existing tags in the
  window and skip duplicates.
- **Gap (active `now`, #265):** local operation log + `--rollback <op-id>`
  (Toggl supports `DELETE /time_entries/{id}`). Spec:
  [`../task-prompts/toggl-posting-task.md`](../task-prompts/toggl-posting-task.md).

### Jira — `gittan jira-sync`

Same pattern, shipped first.

- **Endpoints:** `POST /rest/api/3/issue/{key}/worklog` (post),
  `GET .../worklog` (dedup), `GET /rest/api/3/myself` (credential verify).
- **Issue attribution:** issue keys resolved from git commits / branch names /
  per-profile mapping (`core/jira_sync.py`, `extract_issue_key`).
- **Guardrails:** dry-run, confirm gate, idempotency via a deterministic marker
  embedded in the worklog comment (ADF-parsed on read-back), so re-runs skip
  posted issue/day buckets.
- **Gap:** shares the missing op-log/rollback slice with Toggl (same mechanism
  once #265 lands).

### GitHub — evidence collector (read-only)

- **Endpoints:** public events via `https://api.github.com` (or GitHub
  Enterprise via `GITHUB_API_BASE` → `https://host/api/v3`),
  `collectors/github.py`.
- **Role:** GitHub activity becomes timeline **evidence** (events with
  source/timestamp/detail), feeding classification like any other source. Also:
  repo-slug matching for worktree-invariant attribution
  (`core/github_slug_activity.py`, issue #262).
- **Not built (by design):** no writes to GitHub.

### Briox — manual handoff, no API yet

Invoicing today is: `gittan report` → the personal `/gittan-invoice` skill
produces a Swedish client email + a Briox invoice line + optional day-by-day
Excel. **No Briox API integration exists.** When built, it must follow the same
connector pattern (draft-first invoice, dry-run payload, idempotency, op-log)
and keep the AI-generated per-period description model
(`[[invoice-text-ai-not-config]]` — never static config strings).

### Shared infrastructure (built once, reused by all connectors)

- **Credential onboarding:** `gittan setup` persists tokens to the shell
  profile (`core/setup_shell_profile.py`, `setup_integration_env.py`), with
  **live verify-before-save** (`/myself`, `/api/v9/me`) — a wrong credential is
  never persisted. Env vars always win; `--yes` never prompts for secrets.
- **Readiness:** `gittan doctor` reports per-integration token/workspace
  readiness.
- **`reported_time` bridge:** both syncs can draw candidates from confirmed
  reported time instead of raw report payload (`core/reported_sync.py`,
  `_candidates_from_reported`) — the future default posting path (#263).
- **Testing:** all network calls mocked; no integration test touches a real API.

---

## 2. High-level roadmap toward a SaaS interface

Direction docs:
[`../ideas/conversational-ui-stack.md`](../ideas/conversational-ui-stack.md)
(the CLI **is** the API; conversation-first UX) and issue **#242** (GitHub
Marketplace app, local-first-preserving hybrid). The connector layer above is
deliberately transport-agnostic: candidates → dry-run payload → confirm → post
→ (op-log) works identically whether the confirm click happens in a terminal
or a web UI.

### Phase 0 — harden the local connector core (now)

- Op-log + rollback for Toggl/Jira pushes (#265, `now`) — the audit trail a
  hosted surface will require anyway.
- OS-keychain secret storage (`next` in the Toggl spec) — moves secrets out of
  plaintext shell profiles; a prerequisite for any multi-surface story.
- `reported_time` as the posting source (#263) — confirmed hours, not raw
  evidence, become what leaves the machine.

### Phase 1 — the CLI is the API (no server)

- Structured JSON contracts already exist (`--format json`, `review --json`,
  truth payload v1 via `core/engine_api.py`). An AI runtime / skill layer
  orchestrates commands and renders answers — no MCP, no protocol layer, no
  hosted component. This phase is mostly documentation + skill polish.

### Phase 2 — hybrid hosted surface (GitHub Marketplace app, #242)

- A thin hosted app for **identity + rendering + webhooks**, while evidence
  collection and the source of truth stay local. The web view is the "high
  decision-weight" modal tier (triage, review) from the conversational-UI
  direction — not a data warehouse.
- Connectors run locally; the hosted surface displays candidates/op-log and
  collects the confirm. Payload shapes are already dry-run-printable JSON.

### Phase 3 — SaaS-grade auth & billing connectors

- **OAuth** for Jira/Toggl (currently `do not build yet`) becomes viable once a
  hosted server can hold client secrets and token stores.
- **Briox connector** (draft invoices via API) with AI-generated per-period
  line text as an opt-in, metered add-on — the first monetized connector.
- Multi-workspace / per-session granularity as customer demand appears.

### Invariants that survive every phase

1. Local-first: raw evidence never leaves the machine; summaries do.
2. Push-only, user-confirmed, idempotent, logged, reversible.
3. Draft-first writes; nothing auto-finalizes an invoice.
4. Billable/invoice text is AI-generated per period — never static config.

---

## Traceability

- story_id: none (descriptive product doc, not a task spec)
- related issues: #265 (op-log, `now`), #263 (reported-time layer), #262
  (repo-slug attribution), #242 (Marketplace hybrid), #294 (packaging)
- related specs:
  [`../task-prompts/toggl-posting-task.md`](../task-prompts/toggl-posting-task.md),
  [`../specs/scheduled-reported-time-bridge.md`](../specs/scheduled-reported-time-bridge.md),
  [`../ideas/simple-invoicing-model.md`](../ideas/simple-invoicing-model.md),
  [`../ideas/conversational-ui-stack.md`](../ideas/conversational-ui-stack.md)
- created_at: 2026-07-17
- last_updated_at: 2026-07-17
