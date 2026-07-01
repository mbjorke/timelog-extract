# Work-unit v2 — greenfield architecture (engineering design)

Status: **draft**

Elaborates [`work-unit-config-v2.md`](work-unit-config-v2.md) §3 ("Greenfield model —
implementation sketch") into a buildable engineering design. This is the **how**; the product
**what/why** and the sacred contract live in the decision doc and must not be re-litigated here.

Related: [GH-222](https://github.com/mbjorke/timelog-extract/issues/222) ·
[`work-unit-v2-task.md`](../task-prompts/work-unit-v2-task.md) (canonical backlog — this doc
feeds **item 1** spike and **item 5** schema/migrator; it does **not** change priorities or
promote item 7).

Example names are **neutral** (`customer-a.example`, `portal-repo`). No live customer data.

---

## 1. Purpose & non-goals

**Purpose:** give the spike and the future schema/migrator a concrete target — a config model,
a classifier contract, and a reuse-vs-replace line against the current engine — so
implementation is mechanical rather than exploratory.

**Non-goals:**

- Changing the **sacred contract** (the `gittan report` Project-hour review table — see
  decision doc "Report output we must preserve"). The model below is judged *only* by whether
  it reproduces that table.
- Reordering the backlog. The **spike (item 1) is still the gate**; "total refactor" (item 7)
  stays *do not build yet* until the spike has a verdict.
- Rewriting collectors, the session engine, or the CLI in this design. Those are explicitly
  **kept** (§4).

---

## 2. Why v1 tangles three concerns (the root cause)

A v1 profile (`core/config.py::normalize_profile`, line 162) is one flat record that fuses
three independent concerns:

| Concern | v1 field(s) | What it should be |
|---------|-------------|-------------------|
| **Match signals** — what evidence belongs to this work | `match_terms`, `tracked_urls` | correlation only |
| **Line identity** — what the report line is called | `name` | the invoice line label |
| **Billing bucket** — who is invoiced | `customer` (defaults to `name`) | the rollup row |

`classify_project(text, profiles, fallback)` (`core/domain.py:59`) returns a single **line
key** = `profile["name"]`, scored by per-event string matching (path-like term 2.0,
`tracked_urls` fragment 2.0, profile `name` present +1.0, generic tool term 0.25). The report
then **groups lines by `customer`** for the rollup.

Because the three concerns share one record, `gittan map` creating a slug-named profile (e.g.
a repo-leaf slug like `portal-repo`) with a default `customer` does two kinds of damage at once:

1. the slug term **outranks** the canonical line in `classify_project`, stealing classification;
2. its default `customer` **mis-buckets** the hours away from the real invoice customer.

v2's core move: **split these three concerns** so signals can grow without renaming a line or
re-bucketing a customer.

---

## 3. Model

```text
Customer                      → rollup row in the sacred table (customer-a.example)
    └── WorkUnit (line)        → child line under the customer (· portal-repo)
            ├── primary        repo | ticket | name        (+ billing_granularity)
            ├── signals        repo slugs, hosts, cwd, branches, session-title terms, urls
            └── customer_ref   the billing bucket — owned here, never inferred from a signal
```

- **Customer** — the invoice bucket and the rollup row. Owns its work units.
- **WorkUnit** (the report *line*) — `primary` is the line's identity:
  - `repo` (default per decision doc §2) — label like `portal-repo`, anchor `owner/repo`;
  - `ticket` — label like `GH-196`, anchor `JIRA-123` / `GH-196` (when
    `billing_granularity = ticket`);
  - `name` — free-text line when neither repo nor ticket fits.
- **signals** — *correlation evidence only*. A new repo slug, host, cwd, or session-title term
  attaches **here**, to an existing unit, instead of spawning a new line. Signals never define
  the line label and never define the customer.
- **customer_ref** — resolved from the unit's parent. There is **no path** by which a matched
  signal sets the customer; this structurally prevents the v1 mis-bucket.

**Mapping to the sacred table** is direct: each `Customer` is a rollup row; each `WorkUnit` is
a `· line` with hours and day-count; unmatched evidence still lands in the explicit
`Uncategorized` bucket.

```text
Project-hour review (YYYY-MM-DD to YYYY-MM-DD)
                      Hours  Days
customer-a.example     X.Xh        (Customer rollup)
  · portal-repo        X.Xh  N     (WorkUnit, primary=repo)
  · faq-engagement     X.Xh  N     (WorkUnit, primary=name)
Uncategorized          X.Xh  N
```

---

## 4. Classifier contract

A new classifier replaces `classify_project` but keeps the parts of its scoring that work.

- **Input:** an event's text/anchors (detail, session title, working dir, repo slug, url host)
  — the same material v1 reads.
- **Output:** a **work_unit / line key**. The **customer is derived** from that unit's parent
  — *not* from the matched term. This is the contract's load-bearing rule.
- **Scoring (carried over from v1, retargeted):** path-like / repo-slug signals weigh more than
  generic tool terms; url-host fragments are strong; explicit anchors (repo, cwd) outweigh
  free-text title hits. Score is computed **per WorkUnit over its `signals`**, so adding a slug
  to an existing unit strengthens that unit rather than creating a competitor.
- **Tie-breaks:** highest specific-signal score wins; on a tie, prefer the unit with an explicit
  anchor match (repo/cwd) over a title-only match; then the unit with more distinct matched
  signals. Define deterministically so reports are reproducible.
- **Fallback:** no unit clears the threshold → **`Uncategorized`** (preserved as an explicit,
  visible bucket — never silently absorbed).

**Anti-duplicate invariant:** there is no operation in the classifier or in any attribution UX
that creates a *new* line whose identity is only a repo slug when an existing unit already
carries signals for that slug. (This is the structural fix for the slug-only-duplicate class of
failures and ties to task item 4's "no new slug-only profile" acceptance.)

---

## 5. Engine: reuse vs replace

The "engine room" stays; only attribution + config change.

| Layer | Decision | Where |
|-------|----------|-------|
| Collectors (one per source) | **Reuse** | `collectors/*.py`, `core/pipeline.py`, `core/collector_registry.py` |
| Session / gap math, hour flooring | **Reuse** | `core/domain.py::compute_sessions`, `session_duration_hours` |
| Aggregation → project reports | **Reuse** | `core/report_aggregate.py:23`, `core/project_hours.py::build_project_reports_from_sessions` (line 147) |
| Report rendering, narrative, PDF, HTML | **Reuse** | `outputs/*.py` |
| truth_payload consumers (extension, invoice) | **Reuse** (with §6 versioning) | `core/truth_payload.py`, `core/engine_api.py` |
| Worklogs | **Reuse** | worklog collector + enrich |
| **Config schema + loader** | **Replace** | `core/config.py::normalize_profile` (162), `load_profiles` (285) |
| **Classifier** | **Replace** | `core/domain.py::classify_project` (59) |
| **All v1 map / review / merge / consolidate flows** | **Retire or replace** (preview-only attribution) | `gittan map`, `gittan review`, setup mapping wizards |

The replacement classifier must slot into the existing seam: it still sets `event["project"]`
(the line key) before `aggregate_report()`. Customer rollup grouping is then a lookup
`line → customer_ref`, replacing v1's per-profile `customer` field read.

---

## 6. truth_payload evolution

Today each event carries `project` (the line key) and the payload is `version = "1"`
(`core/truth_payload.py:11`). v2 conceptually wants `line` / `work_unit_id`.

**Proposal (deferred to task item 5, recorded here):** bump `TRUTH_PAYLOAD_VERSION`, add
`line` / `work_unit_id` and `customer` keys, and **keep `project` as an alias** of the line key
for one major version so the Cursor extension and invoice flows don't break. Document the
deprecation window. Semantics (per-window line totals, sessions/events with a line key,
collector status) stay stable — only names and the version field move.

---

## 7. Migration bridge (v1 → v2)

A deterministic, lossless-where-possible mapping — a **compatibility bridge, not the vision**:

| v1 profile field | v2 destination |
|------------------|----------------|
| `name` | WorkUnit `primary` (label; type inferred: repo if slug-like, else name) |
| `match_terms`, `tracked_urls` | WorkUnit `signals` |
| `customer` (or its default) | parent Customer / `customer_ref` |
| `canonical_project`, `aliases` | signals + line label history |

During migration, **detect thin slug duplicates** — a profile whose `name` is only a repo leaf
with ≤N terms while another profile already carries richer signals for the same slug — and
**collapse** them into the canonical unit instead of emitting two lines. This is the same check
task **item 2** (`gittan doctor`) surfaces as a warning; the migrator and doctor should share
one detection function.

Validation: round-trip on an **anonymized fixture** under `tests/`; the migrated config must
produce a report table identical in **shape** to v1 for the sacred contract.

---

## 8. How the spike (item 1) validates this design

The spike is the cheapest possible proof of §3–§4, **not** v1 config-tuning:

1. Build a **minimal new-model classifier** (signals → WorkUnit → customer_ref) over a
   **copied** config — same collectors, same session math.
2. Re-run the operator's acceptance-window report (`--projects-config <copy>`).
3. **Pass** = the sacred table matches the operator-local acceptance file (e.g. the documented
   Uncategorized cluster drops toward ~0 and resolves to the correct customer + existing line)
   **with no new slug-only line created**.
4. **Fail** = record NO-GO; the larger build does not proceed without a new product-owner pass.

Hand-editing v1 `match_terms` in a copied JSON is **explicitly not** the proof — it exercises
the model being retired and demonstrates nothing about v2. Operator-specific customers, hours,
and the acceptance table stay in the operator-local file, never in this repo or PR text.

---

## 9. Open questions (architectural)

Carried from decision doc §8, scoped to this design:

- [ ] Minimum line granularity when `billing_granularity = ticket` — always show the ticket line?
- [ ] Can `Uncategorized` be **pre-split** by suggested customer/line before the operator acts
  (feeds task item 4 preview UX)?
- [ ] Parallel v2 config file alongside v1, or a single breaking migration with the bridge in §7?
- [ ] One attribution command, or none (fully implicit detection + doctor warnings)?

---

## Changelog

- 2026-06-30: Draft. Greenfield architecture for work-unit v2 (story `GH-222`); elaborates
  `work-unit-config-v2.md` §3 into a buildable design (model, classifier contract, reuse/replace,
  migration bridge, truth_payload versioning). Spike remains the gate; no backlog reprioritization.
