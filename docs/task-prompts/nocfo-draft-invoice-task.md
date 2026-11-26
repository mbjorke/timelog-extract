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
  keyed by contact + period. A `pending` row is written before each POST and
  `created` / `rejected` after it. `created` and `pending` (unknown outcome:
  timeout, 5xx, 408, 409) block a repeat until `--force-new`; only a refusing
  4xx allows a retry. Each POST also carries NoCFO's `Idempotency-Key`; a
  `--force-new` retry of an unfinished attempt with the same body reuses its
  key, so NoCFO replays the first draft (within 24 h) instead of creating another.
- **D6 — Draft only.** The client has a create call and a read call. No accept,
  send, paid or delete call exists in Gittan, and a payload that sets `status`
  is refused.

---

### NoCFO draft invoice MVP — `gittan nocfo-invoice`

- priority: **now**
- acceptance:
  - `--dry-run` previews the draft rows per contact and makes no network call.
  - A real run prints the exact payload (with product price and VAT) before asking.
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

### Verify against a live account

- priority: **next** (blocks a real customer invoice)
- Row and invoice fields follow NoCFO's published OpenAPI schema
  (`InvoiceRequest`: `receiver`, `invoicing_date`, `payment_condition_days`;
  `InvoiceRowRequest`: `name`, `unit`, `amount` = unit price, `vat_rate`,
  `vat_code`, `product_count` = quantity, optional `product`, `description`).
  Name, unit, VAT-exclusive price and VAT are copied from the NoCFO product
  read just before the draft; Gittan only supplies `product_count`.
- Still unchecked on a real account: whether the row `amount` is read as
  VAT-exclusive. First live run: one draft for a test contact, open it in NoCFO.

### Later

- `gittan doctor` row for NoCFO token readiness.
- Attach the approved hours report (PDF) to the draft, if the API allows it.
- Read back draft status (accepted / sent / paid) for the effective hourly rate.
- Partner OAuth instead of a personal token — `do not build yet`.

## Traceability

Live verification against a real NoCFO account is still open (see "Verify
against a live account" above), hence `conditional GO`.

- story_id: GH-585
- spec_status: draft
- implementation_status: built
- created_at: 2026-11-26
- last_updated_at: 2026-11-26
- implementation.pr: #585
- implementation.branch: task/nocfo-draft-invoice
- implementation.commits: []
- validation.evidence: tests/test_nocfo_invoice.py (synthetic data, all network calls mocked); no live NoCFO call yet
- validation.decision: conditional GO
- covers: nocfo-invoice
- related:
  - `core/nocfo_client.py`, `core/nocfo_invoice.py`, `core/cli_nocfo_invoice.py`
  - mirrors `gittan toggl-sync` ([`toggl-posting-task.md`](toggl-posting-task.md))
  - API source: NoCFO's MIT `nocfo-cli` toolkit on PyPI (v1.10.0)
- changelog:
  - 2026-11-26: Initial spec and MVP built (PR #585).
  - 2026-11-26: Review fixes — op-log fails closed on a damaged line; re-check
    before each POST; NoCFO ids kept by `normalize_profile`.
  - 2026-11-26: Rows follow NoCFO's OpenAPI schema (hours in `product_count`,
    price/unit/VAT copied from the product); `payment_condition_days` added;
    op-log writes `pending` before each POST so an unknown outcome blocks a repeat.
  - 2026-11-26: 5xx/408/409 count as unknown outcomes; `Idempotency-Key` header
    added (NoCFO developer docs, using-the-api/idempotency).
  - 2026-11-26: Each `pending` attempt is settled only by its own outcome row, so
    a rejected `--force-new` retry never unblocks an earlier unknown outcome.
  - 2026-11-26: An unsettled attempt is reported before an earlier created
    draft, so a `--force-new` retry after a lost response reuses its own key.
  - 2026-11-26: A `created` row settles every attempt that sent its key, so a
    successful same-body retry clears the earlier unknown outcome.
