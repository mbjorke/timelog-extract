# Brainstorm: report-first work units (agenda handout)

**Decision doc:** [`docs/decisions/work-unit-config-v2.md`](../decisions/work-unit-config-v2.md)  
**Canonical backlog (PO):** [`work-unit-v2-task.md`](work-unit-v2-task.md)

**Filled acceptance tables** (real customers, hours, anchors): **operator-local acceptance
file** (e.g. `<operator-config-dir>/work-unit-acceptance.md`) — **do not commit**.

## Ground rule

**Sacred:** the table you get from **`gittan report`** (Project-hour review: customer →
lines → hours → days, plus Uncategorized). Not the **Billable** column (usually `-`).

**Not sacred:** `timelog_projects.json`, **`gittan map`**, merge, `match_terms`,
classify internals — think outside the box.

GH-222 is a symptom (wrong hours in that table), not a requirement to keep map.

---

## 1. Report truth — do this first

Sketch the **correct** Project-hour review for one painful period (e.g. a month), e.g.:

```text
Project-hour review (YYYY-MM-DD to YYYY-MM-DD)
                      Hours  Days
<customer-a>           ?h     ?
  · <line>             ?h     ?
Uncategorized          ?h     ?
```

Fill in customers and **lines** (what the invoice should say, not raw config slugs).

| Case | Customer | Line label(s) | Notes |
|------|----------|---------------|-------|
| Large Uncategorized | | | |
| Duplicate repo / map slug | | | |
| Internal vs billable | | | |
| Target Uncategorized after fix | — | — | ~0h |

Paste the filled table into the operator-local acceptance file
(`<operator-config-dir>/work-unit-acceptance.md`).

---

## 2. Repo vs ticket lines

| Repo-based | Ticket-based |
|------------|--------------|
| Line: `portal-repo-dev` | Line: `GH-196` |
| Invoice from repo | Invoice from ticket |

- Both in one product? ___
- Per customer or per line? ___

---

## 3. Attribution UX — not “map”

How should gaps get fixed so **the next report** is right?

- [ ] Wizard at setup only
- [ ] Fix from Uncategorized in report output
- [ ] Customer-first review queue (not URL-only)
- [ ] New command: ___
- [ ] Mostly automatic + `gittan doctor`

**One sentence:** “When activity is wrong in the report, I want to …”

> Answer (local doc):

**Must never happen without preview of customer + line + hours:**

- [ ] Move hours between customers
- [ ] Create a new line without naming customer
- [ ] Merge duplicate repos into parent without preview

---

## 4. Pain checklist (reference)

- Map created duplicate profile from repo slug (existing line already matched)
- Wrong `customer` on new profile (personal bucket vs invoice customer)
- Large Uncategorized despite anchor nudges
- `gittan review` useless for repo/cwd/title gaps

---

## 5. Output table (required)

| # | Decision |
|---|----------|
| 1 | Invoice **line** unit (repo / ticket / mix) |
| 2 | Tracking vs invoice (same or different?) |
| 3 | Multiple lines per customer (rules) |
| 4 | Target report period + operator-local acceptance file path |
| 5 | Attribution UX sentence |
| 6 | **Close** PR #221 / #223 / #224 (do not merge) — see `work-unit-v2-task.md` |
| 7 | GO spike / v1 guardrails only / defer |

---

## After brainstorm

1. Paste filled tables into the operator-local acceptance file.
2. Track implementation via [`work-unit-v2-task.md`](work-unit-v2-task.md) (Traceability
   lives there — this file is a workshop handout only).

## Traceability

Handout only — canonical traceability is in [`work-unit-v2-task.md`](work-unit-v2-task.md).

- story_id: `GH-222`
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-06-30`
- last_updated_at: `2026-06-30`
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/225
- implementation.branch: `task/work-unit-v2-docs`
- implementation.commits: []
- validation.evidence: see `work-unit-v2-task.md`
- validation.decision: `conditional GO`
- changelog:
  - 2026-06-30: Workshop handout; implementation spec is `work-unit-v2-task.md`.
