# Backlog: NoCFO draft invoices from approved hours (`gittan nocfo-invoice`)

First accounting push target. Gittan proposes hours, the user approves them,
and NoCFO (a Finnish accounting service) receives a **draft** sales invoice
that a human accepts and sends inside NoCFO. Gittan stays out of accounting:
no VAT, no prices, no invoice numbers, no sending.

Product model: [`simple-invoicing-model.md`](../ideas/simple-invoicing-model.md)
(*push-only, dry-run prints the exact payload, explicit confirm, idempotency,
draft-first*). Partner shape: [`partner-briefs/nocfo.md`](../ideas/partner-briefs/nocfo.md).

## Decisions

- **D1 — Input is approved time only.** Rows come from confirmed/edited
  `reported_time` (`gittan reported review` / `reported add`), never from raw
  observed sessions. `Uncategorized` is never invoiced.
- **D2 — Mapping.** Each profile in `timelog_projects.json` may set
  `nocfo_contact_id` (the invoice receiver) and `nocfo_product_id` (an hourly
  product in NoCFO that carries price, unit and VAT). A project needs both, or
  its hours are listed as "not invoiced".
- **D3 — Granularity.** One draft per NoCFO contact per period; one row per
  project + day, so the customer sees the hour basis the user approved.
- **D4 — Auth.** The user's own NoCFO personal API token (`NOCFO_API_TOKEN`)
  and business slug (`NOCFO_BUSINESS`), the same variables NoCFO's own
  `nocfo-cli` reads. Gittan never stores the token. Partner OAuth is
  `do not build yet`.
- **D5 — Idempotency.** Local op-log (`<gittan data dir>/nocfo_oplog.jsonl`)
  keyed by contact + period; a second run skips unless `--force-new`.
- **D6 — Draft only.** The client has a create call and a read call. No accept,
  send, paid or delete call exists in Gittan, and a payload that sets `status`
  is refused.

---

### NoCFO draft invoice MVP — `gittan nocfo-invoice`

- priority: **now**
- acceptance:
  - `--dry-run` prints the draft payload per contact and makes no network call.
  - Without `--dry-run`, each draft needs an interactive yes (default No).
  - Created drafts are logged locally; a re-run for the same contact and period
    is skipped with the earlier draft id.
  - Missing credentials fail with the env var names, before any network call.

```gherkin
Feature: NoCFO draft invoice from approved hours
  Scenario: Dry run shows the payload without calling NoCFO
    Given confirmed reported time for a project mapped to a NoCFO contact and product
    When I run "gittan nocfo-invoice --from 2026-11-16 --to 2026-11-22 --dry-run"
    Then I see one draft per contact with one row per project and day
    And nothing is sent to NoCFO

  Scenario: Unapproved time is never invoiced
    Given proposed (not confirmed) reported time for a mapped project
    When I run the command for that period
    Then that time does not appear in any draft

  Scenario: Confirmed run creates a draft once
    Given I answer yes to "Create this invoice as a DRAFT in NoCFO?"
    When the command runs twice for the same period
    Then exactly one draft is created and the second run reports it was skipped
```

### Verify row field names against a live account

- priority: **next** (blocks a real customer invoice)
- NoCFO's public toolkit passes invoice rows through without a fixed schema.
  The row keys (`product`, `amount` as quantity, `description`) are a best
  reading and live in one place (`core/nocfo_invoice.py`, `ROW_*_FIELD`).
  First live run: create one draft for a test contact, open it in NoCFO, fix
  the constants if a field was ignored.

### Later

- `gittan doctor` row for NoCFO token readiness.
- Attach the approved hours report (PDF) to the draft, if the API allows it.
- Read back draft status (accepted / sent / paid) for the effective hourly rate.
- Partner OAuth instead of a personal token — `do not build yet`.

## Traceability

- story_id: none yet (no GitHub issue)
- spec_status: draft
- implementation_status: built (MVP); live field verification pending
- created_at: 2026-11-26
- last_updated_at: 2026-11-26
- implementation.branch: task/nocfo-draft-invoice
- implementation.pr: pending
- implementation.commits: []
- validation.evidence: unit tests with synthetic data, all network calls mocked
  (`tests/test_nocfo_invoice.py`); no live NoCFO call made yet
- validation.decision: pending
- covers: nocfo-invoice
- related:
  - `core/nocfo_client.py`, `core/nocfo_invoice.py`, `core/cli_nocfo_invoice.py`
  - mirrors `gittan toggl-sync` ([`toggl-posting-task.md`](toggl-posting-task.md))
  - API source: NoCFO's MIT `nocfo-cli` toolkit on PyPI (v1.10.0)
