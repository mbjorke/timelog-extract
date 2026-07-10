# Source-identity blind-spot backlog — 2026-07-10 (product-owner)

Product-owner planning pass converting the blind-spot pass on **source-identity
instability** (comment on #354) into an ordered, behavior-ready backlog. No code
is changed here — this spec is the prioritization record; the filed issues are
the tracked work.

**Decision filter (from `docs/product/gittan-vision.md`):** does the next
`gittan report` / invoice show the operator the *right* hours? Trust and
local-first are non-negotiable. Applied to this family: **silently losing hours
outranks visibly mislabeling them**, which outranks a structurally mitigated
ambiguity.

## Traceability

- story_id: `GH-365`
- spec_status: `draft`
- implementation_status: `not built` (planning artifact — no code)
- created_at: `2026-07-10`
- last_updated_at: `2026-07-10`
- implementation.pr: pending
- implementation.branch: `cursor/blind-spot-unknown-unknowns-c652`
- implementation.commits: []
- validation.evidence: filed issues #366–#369 + their priority labels
- validation.decision: `GO` (as a planning deliverable)
- changelog:
  - `2026-07-10: Initial pass; filed #366 (now), #367/#368/#369 (next); item 3 kept inside #354.`

## Finding: one failure pattern behind six incidents (why this pass exists)

The July 9–10, 2026 incident family — #345 (Cursor agent silent, schema change),
#348 (composerHeaders missing), #351/#353 (Glass PR-tab label overpaint),
#359/#360 (issue-title text parsed into a fake repo slug), #361/#362 (Glass
terminal tabs leak shell commands as session labels), #363/#364 (day-folder
pruning silently drops long-lived Cursor session logs) — shares one pattern:

> The report resolves session labels/identity from **live, mutable third-party
> UI state at report time**. Every fix so far is a **blocklist** against one
> more bad label shape. There is no positive contract for what a valid session
> label *is*, when it is captured, and from where.

Blocklists against a surface Cursor redraws weekly is an arms race. The
blind-spot pass (posted on #354) surfaced five remaining unknown unknowns; this
pass prioritizes them. Item 3 (point-in-time capture — freeze labels on first
sight in the shadow evidence log) is the core of research spike **#354** and is
deliberately **not** duplicated here.

## Prioritization rationale

| Blind-spot item | Issue | Priority | Why this rank |
| --- | --- | --- | --- |
| 2. Silent-source watchdog | #366 | **now** | Hours-loss without alarm, twice in one week (#345, #363); `doctor` said "Logs readable ✓" while turns were dropped. Detection of *absent* evidence is strictly more urgent than fixing *wrong* labels. |
| 1. Label provenance marker | #367 | **next** | Display trust; cheap first slice (anchor metadata + render tweak). Makes any future bad label visible as derived instead of asserted. |
| 5. Enrichment window cap | #368 | **next** | Bounded fix in one module; complements #367 (provenance makes paint visible, the cap makes it small). |
| 4. Multitask tab determinism | #369 | **next** (lowest — effectively P2) | Partially mitigated by #362; #354's findings may change the approach (point-in-time capture could remove live tab reads entirely). |
| 3. Point-in-time capture | — (inside #354) | next (spike) | Already tracked as the research spike's core question; filing a duplicate would split the trail. |

---

## `now`

### #366 — Silent-source watchdog

- priority: now
- problem: a source that produced many events yesterday and zero today — while
  other sources show activity in the same tool — raises no alarm. Both #345 and
  #363 were human-detected; hours were silently lost while `gittan doctor`
  reported the source's logs as readable (`core/doctor_collector_rows.py`
  checks reachability, not liveness).
- user value: trust — the operator learns about missing evidence from the tool,
  not from eyeballing a suspiciously thin report.
- non-goals: fixing any individual collector; building the menu-bar surface
  from `docs/specs/timelog-health-monitor.md` (that spec covers *worklog
  freshness*; this covers *collector liveness* — complementary).
- behavior:

```gherkin
Scenario: Source flatlines while sibling sources stay active
  Given source "Cursor (agent)" produced events on recent days
  And it produces zero events in today's report window
  And other sources show activity overlapping that window
  When the report is rendered
  Then a warning names "Cursor (agent)" as silent
  And gittan doctor shows a liveness row distinct from "Logs readable"
  And the JSON payload marks the source as anomalous in collector_status

Scenario: Genuinely idle day raises no false alarm
  Given no source produced events in the report window
  When the report is rendered
  Then no silent-source warning is shown
```

- acceptance: warning in terminal output (styled per
  `docs/product/terminal-style-guide.md`); doctor liveness row per source; the
  anomaly exposed in `collector_status`; fixture replays of the #345/#363
  conditions trigger it; disabled/opt-in-off sources never do.
- validation: fixture-based tests with neutral data; a manual replay on the
  operator's machine for the two known incident shapes.
- dependencies: baseline store decision — shadow evidence log
  (`~/.gittan/evidence`, #254) vs observed cache vs in-window comparison. The
  alarm must not *require* either store to exist for a yesterday-vs-today check.

---

## `next`

### #367 — Label provenance marker

- priority: next
- problem: a delivery row painted by nearest-neighbor session-label enrichment
  (`core/worklog_enrich.py::enrich_delivery_session_labels`, 2-hour lookback)
  is indistinguishable from a row whose source actually produced that text —
  which is why #351 and #361 kept surprising the operator.
- user value: even when a bad label slips through a blocklist, the reader can
  see it is derived, not asserted by the row's own source.
- non-goals: changing which labels are chosen (that is #368); session math.
- behavior: derived labels carry machine-readable provenance in anchors and the
  JSON payload, and render with a subtle marker per
  `docs/product/terminal-style-guide.md`. (Gherkin in #367.)
- acceptance / validation: see #367.
- dependencies: none; pairs with #368 on the same enrichment path.

### #368 — Enrichment window calibration and cap

- priority: next
- problem: the 2-hour lookback (`_DEFAULT_LOOKBACK_SECONDS`) is uncalibrated
  and unbounded — one session title painted over an hour of GitHub delivery
  rows in a single July 10 report.
- user value: one bad label stays one bad row, not a whole afternoon.
- non-goals: new CLI flags before calibration data justifies one; provenance
  display (that is #367).
- behavior: measure spread (rows painted per label), then cap by time/row count
  and prefer no label over a stale one. (Gherkin in #368.)
- acceptance / validation: see #368.
- dependencies: none technically; sequence after or with #367 so the paint that
  remains is at least visibly derived.

### #369 — Glass/Multitask tab ownership determinism

- priority: next (lowest — effectively P2)
- problem: multiple agents/terminals/PR tabs share the `ownerAgentId` surface
  read by `collectors/cursor_glass_meta.py`; "first non-empty tab label" is not
  deterministic, and the winning tab has repeatedly been the wrong kind
  (#351 PR tabs, #361 terminal tabs).
- user value: a positive allowlist + deterministic tiebreak ends the
  blocklist arms race for this surface.
- non-goals: point-in-time capture (that is #354's spike); reverting #362.
- behavior: only allowlisted tab kinds may name a session; ambiguity resolves
  to *no label* + git-branch fallback. (Gherkin in #369.)
- acceptance / validation: see #369.
- dependencies: **#354 findings may fold this into a different fix** — hold
  implementation until the spike reports, unless a new incident forces it.

---

## Kept inside #354 (not filed)

- **Point-in-time capture** (blind-spot item 3): labels resolve live on every
  report; the shadow evidence log could freeze labels on first sight. This is
  the core question of research spike #354 — filing a separate issue would
  split the decision trail. This pass only references it.

## Open decisions for the maintainer

1. Baseline store for the watchdog (#366): shadow evidence log vs observed
   cache vs window-local comparison. Recommendation: start window-local
   (no new store dependency), upgrade to the shadow log when #254 lands.
2. Sequencing of #367/#368: one combined slice on `core/worklog_enrich.py`
   plus render, or two small PRs. Recommendation: two small PRs, provenance
   first.
3. Whether #369 waits for #354's GO/NO-GO. Recommendation: wait, unless
   another tab-shape incident occurs first.
