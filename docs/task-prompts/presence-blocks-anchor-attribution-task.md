# Presence blocks + anchor attribution (match_terms demoted to fallback)

Successor to [`commit-events-to-shadow-log-task.md`](commit-events-to-shadow-log-task.md).
Changes the unit of attribution from **event** to **time block**: a presence
layer defines when work happened; a small set of **stable anchors** decides
whose block it was; free-text `match_terms` become a tie-breaker of last
resort instead of the load-bearing wall.

## Motivating evidence (2026-07-13 and the config-drift audit)

A verified real-world day exposed both failure classes at once (exact
durations, counts, and identifiers stay in `private/`; shapes only here):

1. **Evidence hole despite full evidence.** A multi-hour client block
   reported as a fraction of its known duration. A sustained stretch of
   registrar/DNS dashboard work left hundreds of raw browser visits on disk,
   but per-URL-per-day thinning collapsed them to a handful of first-visit
   events, and session math (event-density based) evaporated the time.
   Concentrated single-site work is punished; tab-hopping is rewarded.
   (Pipeline bug tracked separately.)
2. **Config drift.** The same audit found, in one pass over one config: a
   tracked project UUID stale after the project moved accounts; the client's
   live site domain absent from `tracked_urls`; an over-broad rule mapping a
   whole messaging platform to one client; a generic geographic match_term
   stealing an event to the wrong project; duplicate profiles for one
   customer; several profiles without `project_id`. None of this was visible
   until manually excavated.

Root cause, one sentence: **match_terms are a hand-maintained cache of world
state, and the world changes without notice.**

## Target architecture

```text
presence layer  ->  time blocks   (when was I working, at what?)
anchor signals  ->  block owner   (whose block was it?)
match_terms     ->  tie-breaker   (only for blocks no anchor can name)
review loop     ->  approval + config suggestions (observed -> classified -> approved)
```

- **Presence layer — the bet is ActivityWatch ingest.** We do not build our
  own capture daemon. ActivityWatch is open source, local-first,
  cross-platform, a decade mature, and its data model maps 1:1 onto block
  needs (`afkstatus` = idle detection, `currentwindow` = app + window title)
  in a plain local SQLite Gittan can read like any other source. A spike
  (2026-07-20) confirmed an own sampler's core is small, but the ongoing
  cost (TCC onboarding, daemon lifecycle, battery, platforms) is exactly the
  wheel AW already owns. Existing dense event sources and the opt-in Timely
  Memory buffer remain valid presence inputs where present. **Hard
  requirement:** every presence provider gets doctor liveness monitoring —
  three silent capture deaths were found in one audit (worklog hook,
  legacy worklog model, and an AW install that had stopped watching months
  earlier); a presence source without a freshness warning is a future hole.
- **Anchors** (stable identity signals): git repo slug, working directory,
  branch, project UUIDs, exact site domains. A few strong signals inside a
  block name the whole block, including its anonymous events (the
  anchor-less dashboard visits inherit the block owner). **Anchor
  attribution is implemented by Work-unit v2 (GH-222 / issue #267,
  `priority:now`, `docs/task-prompts/work-unit-v2-task.md`) — this spec
  consumes that work at block granularity and must not reimplement it.**
- **match_terms fallback**: consulted only when a block has no anchor hit;
  new terms should arrive via the suggestion loop
  (`docs/specs/ab-rule-suggestions.md`), carrying provenance (added-when,
  added-why), not by hand-editing JSON.

## Ordered backlog

### 1. Config-drift health: lint against observed reality

- priority: now
- problem: dead tracked_urls, never-matching terms, cross-project term theft,
  and id-less profiles are invisible until they corrupt an invoice.
- user value: `gittan doctor` / `projects-lint` surface drift while it is
  cheap to fix.
- non-goals: auto-editing config; any new capture.
- behavior:

```gherkin
Scenario: A tracked URL that stopped matching is flagged
  Given a profile has a tracked_url with zero event matches in the last 30 days
  When the user runs projects-lint (or doctor)
  Then the entry is reported as likely stale with its last-match date

Scenario: A match_term that fires across projects is flagged
  Given a match_term contributed events to more than one project's
    classification candidates in the scanned period
  Then the term is reported as ambiguous with per-project hit counts
```

- acceptance: lint gains an observed-reality mode over deduped collector
  events (reuse `projects-audit` machinery); zero-hit tracked_urls, ambiguous
  terms, and profiles lacking `project_id` are each reported; fixture-tested.
- validation: run against a synthetic dataset with planted drift; unit tests.
- dependencies: none.

### 2. Block-based session model behind a flag

- priority: next
- problem: session hours derive from event density, so sparse-evidence work
  evaporates and mixed sessions allocate by event count (known weakness).
- user value: hours reflect presence, not source chattiness.
- behavior:

```gherkin
Scenario: A sparse-evidence block keeps its duration
  Given a contiguous presence block with few but anchored events
  When hours are computed in block mode
  Then the block's duration comes from presence bounds, not event count floors

Scenario: Anchors name a block including its anonymous events
  Given a block containing events with a project anchor hit
  And other events in the block match no profile
  Then the whole block is attributed to the anchored project
  And the attribution notes it was block-inherited (reviewable)
```

- acceptance: `--session-model block` (default unchanged); golden eval
  (`docs/product/accuracy-plan.md`) run in both modes with diff published;
  **payload contract specified before implementation** — whether block mode
  changes existing fields (e.g. `presence_estimated_hours` and its
  not-billable semantics in `core/truth_payload.py`), adds new fields, or
  only annotates attribution, and whether `TRUTH_PAYLOAD_VERSION` bumps.
- dependencies: item 1 (trustworthy anchors require drift-checked config);
  presence density from existing sources is sufficient for a first pass.

### 3. ActivityWatch ingest as opt-in Tier B presence source

- priority: next (after 2)
- problem: work in surfaces that emit no local logs (registrar dashboards,
  waiting, account admin) leaves presence holes.
- approach: read AW's local SQLite (`aw-server/peewee-sqlite.v2.db`,
  `bucketmodel`/`eventmodel`; `afkstatus` + `currentwindow` buckets) as a
  standard collector — same pattern as every other source. See
  `docs/sources/activitywatch-integration.md`.
- non-goals: building our own capture daemon (parked under item 3b); any UI;
  competing presence app.
- acceptance per collector contract (`docs/specs/source-collector-contract.md`):
  off by default, explicit consent, doctor row with disable reason **and a
  freshness/liveness warning when the newest AW event is older than N days**
  (an installed-but-dead AW is worse than none: it looks covered), fixture
  tests against a fixture SQLite, retention via shadow log, metadata only
  (app, title, afk-status), never content.
- dependencies: shadow log (GH-151); AW running on the machine (user-owned).
- known risk (macOS): AW ships x86_64-only macOS binaries (verified against
  0.13.2), so Apple Silicon machines need Rosetta — and a macOS update can
  silently remove Rosetta, killing capture until reinstalled (observed on
  this machine: capture stopped silently in April and the app asked for
  Rosetta again at next launch months later). Doctor's liveness warning is
  the mitigation; the onboarding doc must mention the Rosetta requirement.

### 3b. Own presence sampler

- priority: do not build yet
- rationale: the 2026-07-20 spike proved feasibility (app + idle with zero
  permissions, titles behind one Screen Recording grant, ~100-line core),
  so this is de-risked and parked — not planned. Revisit only if AW ingest
  proves insufficient in practice (e.g. AW unavailable on a target platform
  or its capture granularity fails block mode).
- explicit revisit trigger: Apple has announced Rosetta will be limited
  after macOS 27. If AW still has no native arm64 macOS build by then, its
  macOS capture path dies with Rosetta and this item is the fallback — a
  native sampler is not blocked by that sunset.

### 4. Suggestion loop feeds match_terms with provenance

- priority: later
- problem: fallback terms still rot when hand-edited.
- note: extend `ab-rule-suggestions` flow so accepted suggestions record
  added-when/added-why; lint uses provenance to age entries. Do not build
  until 1–2 have landed and proven the fallback is actually rare.
- precondition: **define the persisted provenance contract first** — the
  current anchor-nudge path (`core/anchor_nudge.py`) writes `match_terms`
  with only `rule_type`/`rule_value`; specify the storage shape for
  added-when/added-why, compatibility with existing plain-string terms,
  migration behavior, and fixtures, so lint aging cannot break existing
  project configs.

### 5. Remove match_terms

- priority: do not build yet
- rationale: fallback naming for anchor-less blocks is still needed;
  revisit only when block mode + suggestions show near-zero fallback usage
  over a full billing cycle.

## Open decisions

- Mixed-session allocation *within* a block (rapid switching between two
  clients) is explicitly not solved by block mode; it needs its own pass
  (relates to `presence-bracketing-task.md` / attended-agent-time work).
- Whether block mode can become default before a presence sampler exists.

## Traceability

- story_id: GH-410 (https://github.com/mbjorke/timelog-extract/issues/410)
- spec_status: draft
- implementation_status: not built
- created_at: 2026-07-20
- last_updated_at: 2026-07-21
- implementation.pr: pending
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-07-20: Initial draft from product-owner pass after the 2026-07-13
    evidence-hole excavation and config-drift audit.
  - 2026-07-21: Presence bet decided: ActivityWatch ingest (own sampler
    parked as do-not-build); anchor implementation delegated to GH-222
    (Work-unit v2) instead of duplicated here; provider liveness warning
    made a hard requirement after a third silent capture death was found.
    AW macOS reality documented: x86_64-only under Rosetta; Rosetta sunset
    (post-macOS 27) recorded as the explicit revisit trigger for item 3b.
