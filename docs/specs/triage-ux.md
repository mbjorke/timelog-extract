# Triage UX

Status: draft — design-sprint output (planning, not implementation)
Last updated: 2026-06-26
Supersedes the paused session in `docs/ideas/triage-design-session-learnings.md`

> This spec is the output of the five-prompt triage design sprint
> (information architecture → interaction model → AI suggestion layer → edge
> cases → component spec). That session was paused pending two grounding
> documents; both now exist, so the sprint resumes here. It is a **product-owner
> planning pass**: an ordered, behavior-ready backlog, not code.

## Why this restarts now

The first design session drifted because its mockups assumed **rich signals
that do not exist** (thread titles, message counts, clean session links). Two
preconditions were named before restarting (`triage-design-session-learnings.md`):

- **A. Real signal examples** — now written: `docs/ideas/triage-signal-examples.md`
  shows what `claude.ai`, `chrome`, and `cursor` events actually look like and
  what high vs low confidence means in practice.
- **B. Setup → triage prerequisite chain** — now largely *built*, not just
  documented. Since the pause we shipped the deterministic backbone the funnel
  needs: the multi-kind **activity anchor** model (`anchors{dir,branch,label}`),
  the unified **`top_signals`** audit model (schema v2), `projects-anchor` /
  `projects-trim` plan executors, and the `status`/`report` unanchored-signal
  nudges with an interactive anchor flow.

The design problem is therefore no longer "invent a triage screen." It is
"**give the deterministic backbone we built one coherent UX across the modal
wall**, and name the boundary where review stops and intent capture begins."

## Vocabulary

- **Triage** = turning *unexplained / unanchored / uncategorized* activity into
  either a **config rule** (`match_terms` / `tracked_urls`) or an
  **attribution** (a session/event assigned to a project), with the user in
  control and nothing written without confirmation.
- **Signal** = a recurring, profile-anchorable value: a web `host`, or an
  activity anchor (`dir` / `branch` / `label`). The unit of `projects-audit`
  `top_signals`.
- **Plan** = a reviewable JSON document of proposed config changes (today:
  trim-plan and anchor-plan; this spec unifies them).
- **Modal wall** (`docs/ideas/conversational-ui-stack.md`) = the decision-weight
  threshold that decides *which surface* renders a triage decision (CLI line →
  Ink overlay → web view).

---

## Prompt 1 — Information architecture

Triage is **not one screen**. It is a single **decision funnel** with three
nested scopes, ordered cheapest-leverage first. The architecture principle:

> **Always triage at the coarsest scope that resolves the most events per
> decision.** Narrow only when the coarser scope is exhausted.

| Scope | Question | Unit | Output | Backbone today |
| --- | --- | --- | --- | --- |
| **Signal** | "What recurring signal isn't mapped to a project?" | `top_signals` row / URL candidate | a config **rule** (one decision maps many future events) | **built**: `projects-audit`, `review`, `projects-anchor`/`-trim` |
| **Session** | "What block of work-time has no confident project?" | a session (≈ `compute_sessions`) with adjacency | a rule (if the session reveals a signal) or an **attribution** | partial: `review --uncategorized` legacy; needs session model |
| **Event** | "This single opaque event has no signal at all." | one event | route to **intent capture**, or accept as opaque time | **out of scope here** — a capture problem, not a review problem |

Two gates bracket the funnel:

- **Upstream — setup gate.** Triage presupposes config; you cannot review
  classifications with nothing to classify against. If config is empty or
  near-empty (first run, ~200 unclassified events), triage routes to
  **bootstrap** (create first projects from the strongest signals), *not* to a
  review queue. This prerequisite chain (`bootstrap → match_terms →
  tracked_urls → audit`) is strictly upstream and must be encoded in the IA.
- **Downstream — the honesty boundary.** The residue that reaches *event scope*
  is, by Document A, often **genuinely unknowable from traces**. The honest
  architecture does **not** send it to a review queue to be guessed at; it
  surfaces it as "opaque time" and points to **intent capture**
  (`docs/specs/intent-capture.md`) as the real fix. Review confirms; it does not
  do archaeology.

The funnel narrows by design: most unexplained time should dissolve at **signal
scope** (map a dir/host once); only the residue reaches **session scope**; only
the truly opaque residue reaches **event scope**, where the answer is "capture
intent next time."

**One data spine.** Everything the funnel produces is either a **plan op over
config** (`op ∈ {add, remove}` of a rule) or an **attribution record**. Signal
scope emits plan-ops; session scope emits plan-ops *or* attributions; event
scope emits intent records. The trim-plan and anchor-plan we already ship are
the same shape with different ops — unifying them (Prompt 5 · Component A) is
the structural backbone of the whole IA.

---

## Prompt 2 — Interaction model

The funnel renders across the **modal wall** by decision weight. Each tier is a
*rendering* of the same plan/candidate data — never a separate capability.

| Tier | Weight | Surface | Triage role |
| --- | --- | --- | --- |
| **0 — Ambient alarm** | none | one CLI line in `status`/`report` | "you have unmapped activity worth ~Xh" — never blocks |
| **1 — Confirm** | low (y/n) | plain CLI / questionary | "Apply this trim? y/n" — one reversible decision |
| **2 — Review-in-place** | medium | React Ink overlay | accept/edit/skip a **batch** of proposals with visible context |
| **3 — Assign-with-context** | high | web view | session-scope assignment of weak-signal blocks with adjacency, sortable tables |

Interaction principles:

1. **One entry verb.** The user (or the conversational layer) says "clean up my
   projects" → a single `gittan triage` dispatcher inspects the audit and opens
   the right *scope* at the right *tier*. The seven legacy `triage*` commands
   (`triage`, `triage-map`, `triage-domains`, `triage-guided`, `triage-apply`,
   …) collapse behind it. `review`, `projects-audit`, `projects-anchor`,
   `projects-trim` remain the stable, scriptable **primitives** underneath.
2. **One direction.** The user is always doing exactly one of: (a) **mapping** a
   signal to a project (adds a rule), (b) **confirming/removing** a stale rule,
   or (c) **attributing** a session. No mode mixes these.
3. **Non-destructive by default.** Every tier produces a plan or writes with a
   backup; dry-run is the default mental model (already the trim/anchor
   contract). Tier 0 writes nothing, ever.
4. **Context travels with the decision.** Tier 2's whole reason to exist is that
   sequential questionary prompts scroll context away. The overlay shows each
   proposal's *why* (signal value, kind, hits, suggested project) in place.
   Tier 3 exists for the one case an overlay can't hold: dense session context.
5. **Always a headless path.** No triage capability may live *only* behind an
   interactive prompt. Tiers 0–2 each have a `--json` read and a plan-file
   apply, so agents and CI use the same funnel.

The modal wall explicitly assigns weak-signal **session** triage to the **web
view** (high weight, dense context). That tier is *not* required for this spec's
first increments — the funnel is fully usable headless via plans long before a
web view exists.

---

## Prompt 3 — AI suggestion layer

Per `docs/ideas/conversational-ui-stack.md`, the AI is **not a classifier**. The
deterministic CLI already produces the bulk of suggestions
(`projects-audit` `top_signals`, `review --json`, rule suggestions). The AI
layer's job is narrow and bounded:

1. **Propose config from natural language.** "The project-beta work lives in the
   dashboard repo" → an anchor-plan op (`add match_terms "dashboard" →
   project-beta`), surfaced for confirmation. NL → **plan**, never NL → silent
   write.
2. **Orchestrate the funnel.** Read the audit, choose the scope, sequence
   proposals by **impact (hours)**, and narrate why ("3 dirs account for ~12h of
   unmapped time this week").
3. **Reformat output.** Turn the resolved report into the shape asked for
   (summary, invoice line, sync payload).

Hard constraints (Truth Standard split — observed → classified → approved):

- The AI may **rank and explain** candidates; it may **not** invent a project,
  nor raise `confidence` above what the deterministic layer assigned.
- Every suggestion carries **provenance**: `origin ∈ {audit, review, nudge,
  ai-nl}` plus the `hits`/`confidence` that justify it, so the user always sees
  *counted fact* vs *model guess*.
- For **genuinely-unknowable** events the AI must **not guess**. It says "this
  is unknowable from traces — tag it at the moment of work next time" and points
  to intent capture. (Re-introducing invented signal is exactly how the first
  design session failed; the AI layer is where that failure would recur.)
- Confidence is presented using Document A's bands (1.0 manual/commit; 0.85–0.95
  strong title / `tracked_urls`; 0.6–0.84 path-fragment; <0.6 adjacency-only;
  `null` unknowable). The AI never shows a confidence the engine didn't produce.

---

## Prompt 4 — Edge cases

| # | Case | Required behavior |
| --- | --- | --- |
| 1 | **First run, no config** (~200 unclassified events) | Detect empty/near-empty config; route to **bootstrap** (offer top-N strongest signals as candidate first-projects), not a review queue. Distinct flow. |
| 2 | **Genuinely-unknowable event** (opaque `claude.ai` thread, unmapped Lovable UUID) | Never fabricate a project. Mark as **opaque time**; show total opaque hours as a hygiene metric; route to intent capture. |
| 3 | **Long-lived thread spanning projects** | Resolve by **time-segmented attribution** via intent-capture re-tag (append-only), not one `tracked_urls` rule. Triage surfaces "this host maps to multiple projects over time — tag per session." |
| 4 | **Nothing to triage** (all signals anchored) | Exit calmly: "everything with real activity is mapped; N opaque hours remain." The nudge register must **not cry wolf**. |
| 5 | **No screen-time / no gap data** | Signal/anchor triage still works (rule hygiene is independent of screen time). Gap-based nudges degrade silently. |
| 6 | **Shared host across projects** (`*.atlassian.test`, Google Docs) | Do **not** auto-map. Flag as **ambiguous — needs explicit anchor**; never a one-click suggestion. |
| 7 | **Conflicting proposals** (dir → A, adjacent host → B for one session) | Present both with evidence; user picks; never silently choose the higher score. |
| 8 | **Idempotent apply** | Applying an `add` for an existing rule is a no-op; a `remove` for an absent rule is `skip (not found)` (already the trim contract). |
| 9 | **Stale plan vs changed config** | Apply validates project names still exist; unknown project without `--allow-create` is an error, not a silent create. |
| 10 | **Non-interactive / agent context** | Every tier has a headless path (`--json` read, plan-file write, `-i` apply). No interactive-only capability. |

---

## Prompt 5 — Component spec

Buildable pieces, mapped to the pending threads.

### A. Unified config-plan model (folds trim + anchor)
One `ConfigPlan` schema replaces the parallel trim-plan / anchor-plan:

```json
{
  "schema_version": 1,
  "note": "human-readable provenance",
  "ops": [
    { "op": "add",    "project_name": "project-alpha", "rule_type": "match_terms",  "rule_value": "project-alpha", "anchor_kind": "dir",  "hits": 42 },
    { "op": "remove", "project_name": "project-beta",  "rule_type": "tracked_urls", "rule_value": "old.example.test" }
  ],
  "meta": { "source": "projects-audit", "window": ["YYYY-MM-DD", "YYYY-MM-DD"] }
}
```

`projects-trim` and `projects-anchor` become two entry points (or one
`projects-apply`) over a single executor; `op` decides add vs remove.
`--write-anchor-plan` / `--write-trim-plan` emit `ops` with the right op.
**Compatibility window:** keep accepting the v1 `removals` / `additions` shapes
(labelled as compatibility-only, per `behavior-contract-standard.md`).

### B. Nudge register (one voice for Tier 0)
A registry of providers, each `() -> Nudge | None`, where
`Nudge = {id, severity, message, action}`. Providers: `unanchored-signals`,
`unexplained-gap`, `uncategorized-share`, `unmapped-url-hosts`, `stale-rules`.
`status` / `report` render the register uniformly (sorted by severity), one
opt-out convention (`--no-nudges` plus per-provider flags). Replaces the bespoke
`build_unanchored_anchors_nudge` / `build_unexplained_gap_nudge` wiring.

### C. Triage dispatcher (`gittan triage`, the one entry verb)
Runs the audit, picks the **scope** (bootstrap if no config; signal scope if
unanchored signals dominate; session scope if uncategorized hours dominate), and
opens the right **tier** (CLI confirm → Ink overlay when available). Legacy
`triage*` commands collapse behind it; primitives stay.

### D. React Ink review overlay (Tier 2)
A renderer over a `ConfigPlan`: a table of ops with context; keys move/edit/skip
(`↑/↓`, `e` edit project, `space` skip, `a` apply-all-remaining, `q` quit);
writes the edited plan back; applies with backup. One overlay reused by signal
scope and session scope. Replaces sequential questionary for batch review.

### E. Session-triage model (Tier 3 feed)
Group uncategorized events into sessions (reuse `compute_sessions`), attach
**adjacency** (nearest high-confidence neighbors), emit **session candidates**
(analogous to `UrlCandidate`). Headless-first; feeds the web view later.

### F. Provenance tagging
Every proposal carries `origin` + justifying `hits`/`confidence` so all tiers
render "why."

---

## Ordered backlog (the deliverable)

### A · Unified config-plan executor
- priority: **now**
- problem: trim-plan and anchor-plan are the same shape with different verbs; two
  validators, two executors, drift risk.
- user value: one mental model ("a plan of ops"), one place to add safety, the
  structural spine every later tier renders.
- non-goals: no new rule types; no behavior change to what add/remove do.
- behavior:

```gherkin
Scenario: One plan carries both add and remove ops
  Given a config plan with an add op and a remove op
  When the plan is applied without --dry-run
  Then the add op inserts its rule
  And the remove op deletes its rule
  And a config backup is written before any change
  And re-applying the same plan is a no-op

Scenario: Legacy trim/anchor plans still apply during the compatibility window
  Given a v1 plan using the legacy "removals" array
  When projects-trim applies it
  Then the removals are applied
  And a deprecation note points to the unified "ops" shape
```

- acceptance: unified executor applies mixed ops with backup; idempotent; legacy
  `removals`/`additions` still accepted with a deprecation note; dry-run unchanged.
- validation: extend `tests/test_projects_audit.py` + a new
  `tests/test_config_plan_executor.py` (add/remove/idempotent/compat).
- dependencies: none (cheapest correctness win; do first).

### B · Nudge register
- priority: **now**
- problem: each Tier-0 nudge is wired by hand; inconsistent voice; no single
  opt-out; easy to "cry wolf" (edge case #4).
- user value: one calm, ranked set of "here's what's worth your attention,"
  uniform across `status` and `report`.
- non-goals: no new detection logic beyond wrapping existing nudges; no GUI.
- behavior:

```gherkin
Scenario: Nudges render uniformly and quiet when nothing is actionable
  Given the unanchored-signals and unexplained-gap providers each return a nudge
  When status renders
  Then both nudges print sorted by severity in one voice
  And --no-nudges suppresses all of them
  And per-provider flags suppress one provider

Scenario: No false alarms when everything is mapped
  Given every signal with real activity is already anchored
  And no unexplained gap exceeds its threshold
  When status renders
  Then no triage nudge is shown
```

- acceptance: providers return `{id,severity,message,action}` or `None`;
  `status`/`report` render via the register; `--no-nudges` + per-provider flags;
  existing anchor + gap nudges migrated with unchanged thresholds.
- validation: `tests/test_report_nudges.py` (register ordering, suppression,
  quiet-when-clean); keep `UNANCHORED_ANCHOR_NUDGE_MIN_HITS` semantics.
- dependencies: none; complements A.

### C · `gittan triage` dispatcher verb
- priority: **next**
- problem: seven `triage*` commands; users can't tell which to run; the funnel
  has no single front door.
- user value: "clean up my projects" → the right scope opens automatically.
- non-goals: not removing the primitives; not the Ink overlay itself.
- behavior:

```gherkin
Scenario: Dispatcher routes first run to bootstrap
  Given an empty project config and unclassified activity
  When the user runs "gittan triage"
  Then it offers to create first projects from the strongest signals
  And it does not open a review queue

Scenario: Dispatcher opens signal scope when unmapped signals dominate
  Given configured projects and unanchored signals above threshold
  When the user runs "gittan triage"
  Then it opens signal-scope review over a config plan
  And legacy triage* commands print a pointer to this verb
```

- acceptance: scope selection (bootstrap / signal / session) from audit state;
  legacy commands deprecated toward it; headless `--json` plan output.
- validation: `tests/test_cli_triage_dispatch.py` (scope routing, deprecation
  pointers, `--json`).
- dependencies: A (renders a plan), B (entry nudge links here).

### D · React Ink review overlay (Tier 2)
- priority: **next**
- problem: sequential questionary scrolls context away for batch review.
- user value: accept/edit/skip a batch of proposals with each one's *why* visible.
- non-goals: no web view; no AI in the overlay; same data contract as the plan.
- behavior:

```gherkin
Scenario: Review a plan in the overlay and apply
  Given a config plan of add ops with context
  When the user opens the Ink review overlay
  And accepts some ops, edits one project name, and skips one
  Then applying writes only the accepted/edited ops with a backup
  And skipped ops are dropped from the applied plan
```

- acceptance: overlay renders a `ConfigPlan`, edits write the plan back, applies
  via the unified executor (A) with backup; full keyboard control; falls back to
  questionary where Ink is unavailable.
- validation: component tests for the overlay + an integration test that the
  applied config matches the edited plan.
- dependencies: A (the executor), C (the verb that opens it), stack decision
  (React Ink TUI) in `conversational-ui-stack.md`.

### E · Session-triage model + candidates
- priority: **later**
- problem: weak-signal blocks need session granularity + adjacency, which signal
  scope can't express.
- user value: assign a 45-min opaque block by *seeing* its confident neighbors.
- non-goals: not the web view UI; headless candidate model only here.
- behavior:

```gherkin
Scenario: Uncategorized events group into one session candidate with adjacency
  Given 120 uncategorized cursor events in one 2-hour window
  And confident GitHub events for project-alpha on either side
  When the session-triage model runs
  Then it emits one session candidate, not 120 rows
  And the candidate lists the adjacent confident project-alpha events as context
```

- acceptance: `compute_sessions`-based grouping; adjacency attached; session
  candidates serializable like `UrlCandidate`; read-only.
- validation: `tests/test_session_triage.py` (grouping, adjacency, no PII in JSON).
- dependencies: A/C; informs the eventual web view.

### F · Web view for high-weight session assignment (Tier 3)
- priority: **do not build yet**
- problem: dense-context session assignment exceeds an overlay's capacity.
- user value: sortable tables, session context, batch assignment.
- non-goals / blockers: depends on intent capture maturing (edge cases #2/#3),
  on E, and on the private-first web-view decisions in
  `conversational-ui-stack.md`. Build only after the headless funnel is proven.

### G · AI natural-language config proposer
- priority: **do not build yet**
- problem: "the project-beta work is in the dashboard repo" should become a plan.
- blockers: depends on the conversational layer / `gittan chat` decision and on
  A (it emits a `ConfigPlan` op). Must obey Prompt 3 constraints (proposal only,
  provenance, never guess unknowables).

---

## Consolidated behavior contract

```gherkin
Feature: Triage UX
  One decision funnel turns unexplained activity into trusted config or
  attributions, rendered across the modal wall, never writing without consent.

  Background:
    Given a local projects config and collected events for a date range

  Scenario: The coarsest resolving scope is chosen first
    Given unanchored signals account for most unexplained hours
    When triage runs
    Then it opens signal scope before session scope
    And resolving one signal maps many future events

  Scenario: First run routes to bootstrap, not a review queue
    Given an empty project config and unclassified activity
    When triage runs
    Then it offers to create first projects from the strongest signals

  Scenario: Genuinely-unknowable activity is not guessed
    Given an opaque conversation event with no signal and no adjacency
    When triage reaches it
    Then it is reported as opaque time
    And triage points to intent capture as the fix
    And no project is fabricated for it

  Scenario: Nothing actionable means no nudge
    Given every signal with real activity is anchored
    When status renders
    Then no triage nudge is shown

  Scenario: Every write is reversible and consented
    Given any triage tier proposes config changes
    When the user applies them
    Then a config backup is written first
    And dry-run shows the same changes without writing
```

## Scenario → evidence mapping

| Scenario | Evidence |
| --- | --- |
| One plan carries add and remove ops | `tests/test_config_plan_executor.py` (pending) |
| Legacy plans still apply | `tests/test_projects_audit.py` (extend) |
| Nudges render uniformly / quiet when clean | `tests/test_report_nudges.py` (extend) |
| Dispatcher scope routing | `tests/test_cli_triage_dispatch.py` (pending) |
| Overlay apply matches edited plan | overlay component + integration test (pending) |
| Session candidate with adjacency | `tests/test_session_triage.py` (pending) |
| Existing anchor flow (Tier 1) | `tests/test_anchor_nudge.py`, `tests/test_collectors_claude_code_context_dir.py` |

## Non-goals

- Not a classifier rewrite and not a new confidence model — triage renders what
  `classify_project` and the audit already produce.
- No cloud backend; no auto-write without explicit confirmation.
- Does not replace intent capture; it defines the boundary where review stops.
- No mobile UI (messaging-gateway intent capture is the remote stopgap).

## Open decisions

1. `projects-apply` (one command, `--op`) vs keeping `projects-trim` /
   `projects-anchor` as thin wrappers over the unified executor.
2. Nudge severity scale (info / warn / act) and default ordering.
3. Where the dispatcher draws the signal-scope vs session-scope line (hours
   threshold vs signal-count threshold).
4. React Ink stack confirmation and its fallback contract on non-TTY.
5. Whether accepting an attribution may optionally write a durable rule, or stay
   a separate evidence stream (mirrors the open question in `intent-capture.md`).

## Related

- `docs/ideas/triage-design-session-learnings.md` — why the first session failed;
  the five-prompt structure reused here.
- `docs/ideas/triage-signal-examples.md` — Document A; the real signal grounding.
- `docs/specs/intent-capture.md` — the upstream fix for weak signals; the
  event-scope boundary of this funnel.
- `docs/ideas/conversational-ui-stack.md` — the modal wall and stack direction.
- `docs/specs/working-directory-anchor-signal.md` — the anchor / `top_signals`
  backbone the funnel renders.
- `docs/ideas/fast-project-mapping-playbook.md` — the manual workflow triage
  improves on.
- `docs/product/cli-command-map.md` — canonical command language and the
  setup → review chain.
