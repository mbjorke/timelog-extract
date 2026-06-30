# Work-unit model v2 — brainstorm + greenfield (report-first)

Status: **draft — conditional GO on operator spike**

Related: [GH-222](https://github.com/mbjorke/timelog-extract/issues/222) (symptom: bad paths
*into* the report), [`work-unit-v2-task.md`](../task-prompts/work-unit-v2-task.md) (canonical
backlog), [`work-unit-brainstorm-agenda.md`](../task-prompts/work-unit-brainstorm-agenda.md)
(workshop handout).

Historical v1 UX notes (non-binding): [`map-customer-first-flow.md`](../task-prompts/map-customer-first-flow.md),
[`map-existing-project-and-merge-ux.md`](../task-prompts/map-existing-project-and-merge-ux.md).

**Operator-specific acceptance tables** (real customers, hours, anchors) live **outside the
repo** — in an **operator-local acceptance file** (same directory as `timelog_projects.json`,
e.g. `<operator-config-dir>/work-unit-acceptance.md`). Do not commit those rows.

---

## Sacred contract: `gittan report` output only

**Everything else may be redesigned or deleted** — including:

- `timelog_projects.json` shape and field names
- `classify_project()` / `match_terms` mechanics
- **`gittan map`** (command name, flow, merge, post-report prompts)
- `gittan review`, setup mapping wizards, duplicate-family logic
- Collector implementation details (as long as evidence still feeds the report)

**Not sacred:** how operators *configure* attribution. Only the **observable report
result** operators trust for invoicing and reconciliation.

### Report output we must preserve (terminal)

The **Project-hour review** table for a date window:

```text
Project-hour review (YYYY-MM-DD to YYYY-MM-DD)
                      Hours  Days
<customer>             X.Xh      (rollup)
  · <line>             X.Xh  N   (one or more lines per customer)
...
Uncategorized          X.Xh  N   (explicit bucket when unknown)
```

Properties that matter to users:

| Property | Why |
|----------|-----|
| Grouped by **customer** (invoice bucket) | Matches outward billing |
| **Lines** under customer with **hours** and **day count** | Invoice lines / Briox / email |
| **Uncategorized** visible | Forces reconciliation; must not silently absorb noise |
| Evidence legend / source transparency | Trust in the number |

**Not sacred:** the terminal **Billable** column (often `-` when `--billable-unit` is off).
Rounding to billing units belongs in invoice tooling, not the default review table.

### Report output we must preserve (machine)

`gittan report --format json` / `truth_payload` spine (version may evolve, semantics not):

- Per-window **project totals** (hours per classified line name)
- **Sessions** and **events** with a `project` (or equivalent line key) on each event
- **Collector status** / date bounds / config path metadata for reproducibility

Extensions and invoice flows depend on this. **Line names** in the report may map to
repo, ticket, or engagement id in v2 — but the *shape* of the table stays familiar.

### Brainstorm rule

Start from a **desired report for a real period** (correct customers, lines, hours).
Work backward:

1. What should each line be? (repo / ticket / name)
2. What evidence must attach to that line?
3. What operator action fixes gaps? (**Not** “how do we patch map?”)

Record filled tables in **local operator docs** (operator-local acceptance file; not in
repo).

---

## Why v1 broke (context, not a design anchor)

v1 stuffed customer, engagement, and signals into `name` + `match_terms`. Paths like
**`gittan map`** edited that blob and often:

- created a **new profile** from a repo slug when an existing line already matched;
- set **customer** to a personal/default bucket instead of the invoice customer;
- **merged** duplicate families toward a parent and moved hours between invoice buckets.

GH-222 describes that pain; **the fix is not “better map”** unless it reliably produces
the sacred report table.

---

## 1. Brainstorm outcomes (generic)

### Participants

- **Operator** who runs `gittan report` for invoicing (often solo on this product)
- Optional: agent as note-taker — async, no workshop timebox required

### Product decisions (portable)

| # | Question | Direction |
|---|----------|-----------|
| 1 | **Invoice line** unit | **Repo** default; ticket per work unit when configured |
| 2 | **Tracking** vs invoice | **Same** as report line unless explicitly split later |
| 3 | Multiple lines per customer | When engagements differ (e.g. prod vs dev); operator decides per customer |
| 4 | Target report for spike | **Local acceptance doc** — date range + customer/line/hour table |
| 5 | **Attribution UX** | From Uncategorized / anchor nudge → pick **customer + existing line** → preview hours |
| 6 | **Never without preview** | Move hours between customers; merge into parent; create line without naming customer |
| 7 | Open PRs (#221–224) | **Park** until spike passes operator acceptance |

### Sequence (order matters)

1. Report truth — fill local acceptance table
2. Repo vs ticket (§2)
3. Work unit model (§3)
4. Attribution UX (§4)
5. Spike GO / NO-GO (§9)

### Pain patterns (generic)

| Pattern | Wrong today | v2 intent |
|---------|-------------|-----------|
| Large **Uncategorized** | Evidence unmapped | Assign to correct **customer + line**; bucket → ~0 |
| **Map “new project”** from repo slug | Duplicate profile steals classification | Attach anchor to **existing** line only |
| **Consolidate** duplicate repos | Hours roll to parent | Preview; never silent cross-customer move |
| **URL review** for anchor gaps | `gittan review` finds no hosts | Anchor attribution (repo, cwd, title) is a different surface |

---

## 2. Invoice granularity: repo vs ticket

| | **Repo-based** (common default) | **Ticket-based** (common elsewhere) |
|---|--------------------------------|-------------------------------------|
| Report line label | `portal-repo-dev` | `GH-196` |
| Invoice text | “Portal dev — 12 h” | “GH-196 — 4 h” |
| Identity anchor | `owner/repo` | `JIRA-123` / `GH-196` |

Both are **lines under a customer** in the sacred table. Product supports both via
`billing_granularity` per work unit (or per customer default).

---

## 3. Greenfield model (implementation sketch — not sacred)

> **Engineering design:** elaborated into a buildable architecture in
> [`work-unit-v2-architecture.md`](work-unit-v2-architecture.md) (config model, classifier
> contract, reuse-vs-replace, migration bridge).

Internal config may look nothing like v1. Conceptual model:

```text
Customer          → row in report rollup (customer-a.example, …)
    └── Work unit     → child line (· portal-repo, · faq-engagement, …)
            ├── primary     repo | ticket | name
            └── signals     correlation (hosts, cwd, branches, secondary slugs)
```

Classification serves **report lines**, not JSON elegance.

### Examples (neutral)

- `customer-b.example` → `· portal-repo` (master repo line).
- `customer-a.example` → `· faq-engagement` when evidence mentions a prospect name but
  **customer** is the operator’s billing bucket (internal or won customer).

---

## 4. Attribution UX (replaces “gittan map” in planning)

**Do not assume** the v1 `gittan map` command, post-report duplicate merge, or
`match_terms` editing.

| Approach | Delivers |
|----------|----------|
| **Report-gap fixer** | From Uncategorized / nudge → pick customer + line → preview hours impact |
| **Setup once** | Customer + work units at onboarding; runtime is read-only |
| **Review queue** | Customer-first queue (not URL-only review) |
| **Implicit** | Strong repo/ticket detection; operator edits rare |

Success metric: **next `gittan report` shows the right table**, not “config file updated”.

If a command remains called `gittan map`, it is one implementation option — not the
product definition.

---

## 5. Relation to v1 (migration only if v2 approved)

| v1 (legacy) | v2 direction |
|-------------|--------------|
| `timelog_projects.json` projects[] | customers + work_units (or equivalent) |
| `match_terms` soup | primary + signals |
| `gittan map` merge/consolidate | **retire** or replace with preview-only attribution |
| `classify_project()` | new classifier targeting report line keys |

Migrator is a **compatibility bridge**, not the vision.

---

## 6. What we likely keep (engine room)

Evidence collection, session gap rules, hour flooring, report rendering pipeline,
`truth_payload` consumers, worklogs, PDF — **if** they still produce the sacred table.

Replace freely: config schema, classification rules, all v1 mapping/review flows.

---

## 7. Open PRs / issues

Disposition decided 2026-06-30 — **close, do not merge** (see
[`work-unit-v2-task.md`](../task-prompts/work-unit-v2-task.md) § Open pull requests):

| Item | Decision |
|------|----------|
| [#221](https://github.com/mbjorke/timelog-extract/pull/221) | **Close** — red CI; map scope; cherry-pick collectors later if needed |
| [#223](https://github.com/mbjorke/timelog-extract/pull/223) | **Close** — v1 map UX superseded; branch for local use only |
| [#224](https://github.com/mbjorke/timelog-extract/pull/224) | **Close** — superseded doc; v2 docs via new PR |
| [#222](https://github.com/mbjorke/timelog-extract/issues/222) | **Keep open** — umbrella; implementation via `work-unit-v2-task.md` |

---

## 8. Open questions

- [ ] Minimum line granularity in report: always show ticket when `billing_granularity=ticket`?
- [ ] Can `Uncategorized` be split by suggested customer/line before operator acts?
- [ ] Is JSON `project` field renamed to `line` / `work_unit_id` in truth_payload v2?
- [ ] One attribution command or none (fully automatic + doctor)?
- [ ] Parallel config file or breaking migration?
- [ ] Should `gittan doctor` warn on duplicate slug profiles with different customers?

---

## 9. Spike workflow

1. Operator maintains acceptance table in an operator-local file (e.g.
   `<operator-config-dir>/work-unit-acceptance.md`).
2. Copy config (`cp` timestamped backup); experiment on copy or branch config path.
3. Spike — **same collectors → new classifier / attribution → same sacred table**.
4. Pass/fail against local acceptance table (hours tolerance documented there).
5. **Conditional GO** → implementation epic; **NO-GO** → v1 guardrails only.

v1 map PRs stay **parked** until step 4 passes.

**Traceability and backlog items:** [`work-unit-v2-task.md`](../task-prompts/work-unit-v2-task.md).

---

## Changelog

- 2026-06-30: Draft; repo vs ticket billing.
- 2026-06-30: **Report-first** — sacred contract is `gittan report` output; `gittan map` and v1 config are not design anchors.
- 2026-06-30: **Billable** column dropped from sacred table.
- 2026-06-30: Operator acceptance tables stay operator-local; repo doc genericized.
- 2026-06-30: Canonical PO backlog → `docs/task-prompts/work-unit-v2-task.md`.
- 2026-06-30: PR #221–#224 — close without merge; v2 docs via new PR.
