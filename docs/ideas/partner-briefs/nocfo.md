# Partner brief — NoCFO

**Status:** Draft hypothesis — not outreach, not a term sheet.

**Relationship (draft):** Complement. Gittan is the **hour basis upstream of the
invoice**; NoCFO is the accounting and invoicing system. Gittan does not compete
on bookkeeping, VAT or invoicing.

**Last updated:** 2026-11-26

Adapted from the [Timely brief](timely.md): same structure, different
relationship. Timely overlaps with Gittan on evidence capture; NoCFO does not
capture time at all, so the fit is a hand-off, not a design partnership.

---

## Why NoCFO is a good partner

NoCFO serves Finnish small businesses and sole traders with accounting and
invoicing. Many of them are consultants who bill by the hour and today type
hours into an invoice by hand.

- **Gittan brings:** local, privacy-first evidence of where the hours went;
  a review step where the user approves the hour basis; a reproducible,
  inspectable report behind every invoice row.
- **NoCFO brings:** the customer register, products and VAT, invoice numbering,
  delivery (email, e-invoice), bookkeeping. Everything Gittan should not build.

The integration point already exists in public: NoCFO publishes an open-source
toolkit (`nocfo-cli`, MIT) with a REST API and a hosted MCP that can create a
sales invoice as a **draft**.

---

## Product boundary (non-negotiable)

1. Gittan proposes, the user approves, NoCFO does the accounting.
2. Only approved hours leave the machine, as invoice rows. Raw evidence never does.
3. Gittan creates **drafts** only. A human accepts and sends in NoCFO.
4. No prices or VAT in Gittan: rows reference a NoCFO product that carries them.

Shipped as `gittan nocfo-invoice` — see
[`nocfo-draft-invoice-task.md`](../../task-prompts/nocfo-draft-invoice-task.md).

---

## Problem we solve for them (hypothesis)

| Their customer's pain | Gittan angle |
| --- | --- |
| Hours for an invoice are reconstructed from memory at month end | Hours are already observed and approved day by day |
| The customer asks "what did these hours go to?" | Each row is a project + day the user approved, with evidence behind it |
| AI-heavy work is hard to see in a calendar | Collectors for AI/IDE tools (Claude, Cursor, Codex, …) |

---

## Offer shapes (pick one for the first conversation)

1. **Listed add-on (lowest friction)** — Gittan is offered to NoCFO customers
   who bill by the hour, as an optional tool that hands NoCFO a draft invoice.
2. **Supported integration** — NoCFO confirms the API is supported for
   third-party products and offers app registration (OAuth) so users connect
   without pasting a personal token.
3. **Deeper module** — only after there are paying users who came through NoCFO.

**Not proposing:** Gittan reading or writing bookkeeping, or sending invoices.

**License boundary:** Gittan is GPL-3.0-or-later ([`LICENSE`](../../../LICENSE),
[license goals](../../security/license-goals.md)). Shapes 1–2 need no license
change: NoCFO lists or links Gittan, and Gittan only calls NoCFO's API.
Embedding Gittan code in NoCFO's own product (shape 3) would need a separate
commercial license from the copyright holder. Not legal advice; the `LICENSE`
text governs.

---

## Proof plan (if NoCFO says yes)

| Step | Gittan deliverable | Success signal |
| --- | --- | --- |
| 1 | Demo: hours → approved basis → draft in NoCFO (max three screens) | NoCFO sees the flow end to end |
| 2 | `gittan nocfo-invoice` verified against a live account | A real draft with correct rows, no manual fix |
| 3 | A few paying users who invoice through NoCFO | Users keep using it after the first invoice |

---

## Open questions (technical, safe to ask)

- Is the API behind `nocfo-cli` and the hosted MCP supported for third-party products?
- OAuth app registration instead of personal tokens?
- Can a token be limited to draft sales invoices + reading contacts and products?
- Rate limits per token and per business?
- Is the row `amount` read as VAT-exclusive when the product is VAT-inclusive?
- Can a draft carry an attachment, such as the approved hours report?

---

## What stays in `private/`

Contacts, commercial terms, revenue share, targets, timeline and any pitch copy.

---

## References

- [`nocfo-cli` on PyPI](https://pypi.org/project/nocfo-cli/) — NoCFO's own API client and MCP server
- [`simple-invoicing-model.md`](../simple-invoicing-model.md)
- [`external-integrations.md`](../../product/external-integrations.md)
