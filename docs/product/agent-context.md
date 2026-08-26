# Gittan — agent context (read this first)

Compact rules for any agent working in this repo (Cursor / Codex / Claude).
Prefer this file over long chat history.

Process rules live in `AGENTS.md` and win on conflict; this file is **product
vocabulary and product rules**. The maintainer's own copy of this note carries
one section that is deliberately not reproduced here — see *Jira status* below.

---

## Product in one line

Local ledger for professional time: evidence from AI / IDE / Git + context from
Jira → human approve → optional post to worklog or invoice.

Role: **butler** (prepare, never silent-charge) + **pollinator** (move minimal
facts between systems).

---

## Vocabulary (use exactly)

| Term | Meaning |
| --- | --- |
| local-first | Ledger + approve live in the user's **device sphere**. Cloud is fine as a workspace, not as the default SoR for hours. |
| device sphere | All the user's devices, not one laptop. |
| cloud session | Vendor-hosted chat/agent (e.g. a Grok Project); creates traces, does not own the ledger. |
| Project (Grok) | A Grok app folder. Separate from the chat **title**. |
| ledger | events → blocks → approved rows |
| butler | collect, classify, propose; wait for approve before external truth |
| pollinator | carry pollen in either direction via explicit adapters |
| pollen | minimal outbound/inbound facts (issue key, project, `evidence_id`, approved hours) — not raw AI logs by default |
| review-gate | no invoice/worklog truth without approve |
| propose → approve → post | the only allowed "auto billing" model |
| match_terms | primary deterministic project matcher |
| tracked_urls | explicit chat URL → project |
| binding | stable thread / url / title → project |
| evidence_id | idempotent post key |
| Jira → Gittan | context in (plan, labels, billable) — **priority** |
| Gittan → Jira | worklogs out — partial today |
| SoR | system of record for hours = the user's ledger |
| adapter | named edge, e.g. `jira.pull_context`, `jira.push_worklogs` |
| FDE | Forward Deployed Engineer |
| plan vs reality | Jira = plan; Gittan = evidence |
| CRDT / HLC / LWW / append-only | multi-device sync toolkit; use later, not first |

**Naming note:** the code's intent store (`core/intent_store.py`,
`~/.gittan/intent-capture.jsonl`, `gittan intent`) *is* the binding store this
table names. Until they are reconciled, read "binding" and "intent record" as the
same object. See `docs/specs/project-field-detection-signals.md` §9.

---

## Hard rules

**Do**

- Deterministic matching before LLM guessing.
- Keep raw traces local; sync ledger and decisions first.
- Jira context **in** before expanding worklog **out**.
- Idempotent posts (`evidence_id`).
- Explicit adapters per direction.

**Do not**

- Silent auto-debit or auto-post without approve (or strict user rules).
- LLM as the primary project classifier.
- A Gittan cloud as SoR for raw sessions.
- Treat local-first as offline-only or single-machine.
- Build a generic iPaaS without a review-gate.
- Expand scope past evidence → approve → pollen.

---

## Project matching (priority order)

1. `tracked_urls` / explicit binding
2. Specific `match_terms` — long unique strings, e.g. a full chat title
3. Git issue keys / branch keys
4. Weak alone: short names, e.g. a Grok **Project** folder called "Gittan"
5. Worklog manual line as backup truth

A future MCP surface must **write the same binding store**, not a parallel
AI-guess layer.

> **This is a ladder, not a score.** Ranks 1 and 3 are built as tiers in
> `classify_project`: a specific `tracked_urls` match wins outright, then a
> declared `jira_issue_key`. Two things stay additive on purpose — an over-broad
> URL on a shared host (a host hint, not a binding) and an issue key resolved
> only through its project prefix (an inference, not a declaration). Ranks 2 and
> 4 are still the older summed score, and rank 5 is not implemented at all. The
> remaining gap is inventoried as D2, D4 and D5 in
> `docs/specs/project-field-detection-signals.md` §11.

---

## Jira status (code)

- Command: `gittan jira-sync`.
- Direction today: mostly **Gittan → Jira** (POST worklogs).
- Maps the issue via commit message, then branch name.
- Supports `--dry-run` and confirm.
- Has `list_jira_worklogs` (support for posting, not a full pull into `report`).
- Not a report collector.
- Not bidirectional.
- Not yet validated against a real week by its intended user, and the process it
  was built for is undocumented.

Next Jira work: document that process → dry-run a real week → then
`jira.pull_context`.

*(The maintainer's private copy names the user this was built for. Per
`AGENTS.md` → *Documentation privacy and path hygiene*, personal identifiers stay
out of committed docs.)*

---

## Billing

```
collect → propose rows → approve → post(adapter)
```

Modes: `propose` (default) | `auto_approve` under strict rules | never a silent
charge.

---

## Build order

1. Ledger model, bindings, Jira process + context in.
2. Approve store + `evidence_id` posts.
3. Multi-device: append-only + idempotent merge; CRDT/HLC only if real conflicts
   appear.
4. More adapters only when a real process needs them.

---

## One-liners (copy for UI / docs)

- Dina enheter. Din tidslista. Ditt godkännande.
- Jobba var du vill. Tidlistan är din. Inget ut innan du sagt okej.
- Cloud sessions OK. Cloud as SoR for your hours: not by default.
- Butler for the draft. Pollinator between systems.

---

## Need / right to win

**Need:** professional minute-control of **paid work time** — see it, bill it,
defend it, spot margin leaks.

**Win:** sit between the tools and the invoice — neutral evidence + Jira context
+ device-sphere SoR. Not timers, not IDE-only metrics, not model-vendor
observability.

---

When unsure: prefer the smaller change, deterministic behavior, and the
review-gate over new smartness.
