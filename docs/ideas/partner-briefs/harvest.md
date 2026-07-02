# Partner brief — Harvest

**Status:** Draft hypothesis — not outreach, not a term sheet.

**Relationship (draft):** **Complement** — Gittan is evidence + review upstream; Harvest remains time entry + invoice truth for agencies and consultants.

**Last updated:** 2026-07-01

---

## Why Harvest is a dream partner

Harvest is the classic **agency/consultant billing sink**: timers, projects, clients, invoices. Timely's alternatives pages position Harvest as manual-discipline / established agency tooling — a buyer segment that already **pays for time accuracy** but still loses hours to forgotten timers and weak context.

**Gittan brings:** local multi-source dev/AI evidence, defensible narrative, JSON/PDF export after human approval.

**Harvest brings:** trusted billing workflow, client-facing invoices, integrations agencies already use.

**Overlap risk:** Low if Gittan does not try to become a full invoice product on day one.

---

## Problem we solve for them (hypothesis)

| User pain | Gittan angle |
| --- | --- |
| Developers forget timers; billable context lives in IDE/AI/Git | Pre-classified evidence sessions with source + detail |
| Harvest entries lack proof when clients question hours | Export bundle links commits, PRs, URLs, worklog lines |
| Harvest is not built to chase every new AI coding tool | Gittan collector engine absorbs that churn |

---

## Offer shapes (pick one for first conversation)

1. **Import integration** — Approved Gittan sessions → Harvest time entries (API), with notes and external links.
2. **Harvest marketplace / partner listing** — “Developer evidence for Harvest” companion positioning.
3. **Co-marketing to consultants** — collect locally → review in terminal → push approved hours to Harvest.

**Not proposing:** Replace Harvest projects/clients/invoices, or require Gittan cloud.

---

## 90-day proof plan (if either side says yes)

| Week | Gittan deliverable | Success signal |
| --- | --- | --- |
| 1–2 | Map Harvest API time-entry fields to Gittan truth payload | Field mapping doc + one manual import |
| 3–4 | Prototype export (dry-run + explicit confirm before POST) | Idempotent create; no duplicates on re-run |
| 5–8 | 5 pilot users (consultants on Harvest) | Most billable dev hours need no manual timer reconstruction |
| 9–12 | Privacy review + support playbook | Clear consent copy; no surveillance framing |

---

## Integration sketch (technical)

```text
gittan report --from … --to … --format json
  → user reviews / adjusts
  → gittan export harvest --dry-run   # future command
  → user confirms
  → Harvest API: time entries with project_id, notes, spent_date, hours
```

**Idempotency:** stable `external_id` per approved session or work unit (aligns with Timely API benchmark §5 and §7).

---

## Open questions

- Partner-built importers vs in-product “connect Gittan”?
- Project mapping: Harvest project IDs vs Gittan profile names?
- Segment: solo dev-consultants vs agencies?

---

## What stays in `private/`

Customer names, revenue share asks, unpublished pricing.

---

## References

- [Timely vs Harvest (competitive framing)](https://www.timely.com/alternatives/harvest/)
- [`similar-repos-checklist.md`](../../inspiration/similar-repos-checklist.md)
- [`simple-invoicing-model.md`](../simple-invoicing-model.md)
