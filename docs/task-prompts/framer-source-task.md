# Task Story: Framer As A Gittan Source

Product-owner planning pass for adding the Framer design tool as a Gittan
source. This is a **backlog**, not an implementation. It is grounded in a live
probe of a real Framer install (see *Evidence probe* below), because the
feasibility of this source turns entirely on what Framer actually retains
locally — and the answer changes the shape of the work.

## Traceability

- story_id: `pending` (issue not yet created — see Deliverable note)
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-08-18`
- last_updated_at: `2026-08-18`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `NO-GO`
- changelog:
  - `2026-08-18: Initial product-owner backlog created from a live evidence probe.`

## Why this matters

Framer is where design and site-building work happens for users who do not live
in an IDE. Today that work is invisible to Gittan: it produces no IDE artifact,
no commit, and almost no browser history. A user who spends an afternoon in
Framer sees an empty report and concludes Gittan does not find their time —
which is the exact failure mode `docs/product/accuracy-plan.md` exists to
prevent.

The question is not "should Gittan see Framer" but **"what can Gittan honestly
claim to see"**, because Framer's local footprint is unusually hostile to
retroactive reconstruction.

---

## Evidence probe (2026-08-18)

Probed against an installed `Framer.app` (Electron, ~1.3 GB of app support
data), on a day the app was actively used. Findings drive every priority below.

| Candidate signal | Location | Verdict |
| --- | --- | --- |
| Chromium `History` DB | Framer partition | **Absent.** The Lovable-desktop primary path (navigation history) does not exist for Framer. |
| AI agent chat state | `IndexedDB/…framer.com…leveldb`, `keyval` store: `activeChatAgentId`, `scopeId`, `title`, `lastMessageTimestamp` | **Live state only.** 579 decoded `lastMessageTimestamp` values spanned **4 minutes of a single day** — a continuously rewritten CRDT/agent store, not an append-only history. |
| Design-document state | Local Storage `crdt-tree-version:<projectId>`, `framer-recent-spaces` (workspace UUIDs), `VekterUserDefaults` | **Version counters and id lists, no timestamps.** Tells you the document changed since the last sample; never when or how much. |
| OPFS / CRDT files | `Partitions/framer/File System/…` | 13 files, **all mtimes on the probe day**. Coarse "the app wrote something" signal, not retroactive. |
| Framer's own telemetry | Local Storage `framer-tracking-client-queue` | **Drain-on-send buffer.** Observed vocabulary: `app_foreground`, `app_background`, `ui_long_frame`, `error_toast`, `code_generation`, `agent_update_project_tool`. The only retained entries were **stuck events from ~7 months earlier** that failed to send. Not a log. |
| Chrome history | Chrome `Default/History` | **23 visits over 2 distinct days in ~7 weeks**, mostly `api.framer.com/auth`, `/login`, `/welcome`. Real work happens in the app, not the browser. |
| Publish / deploy state | cache, Local Storage, IndexedDB | **Nothing.** Zero publish/deploy/`framer.website`/custom-domain tokens; no cached `api.framer.com` responses; no publish event in the telemetry vocabulary. |

### The two conclusions that shape this backlog

1. **Framer evidence is not backfillable.** Every local signal is live state that
   Framer rewrites or drains. `gittan report --last-month` can never recover
   Framer time that was not captured while it happened. This is precisely the
   retention gap `docs/specs/local-evidence-shadow-log.md` was written for, and
   Framer is the first source where the shadow log is not an improvement but a
   **precondition**.
2. **Publishing is not locally observable.** Publish state lives server-side.
   Detecting it means a network call to the Framer API with account auth — a
   different class of source (opt-in, `delivery_evidence`, like GitHub), not a
   variation on the collector below.

### Evidence role

Framer desktop is `passive_context` with attended semantics in v1 — the same
posture as `Lovable (desktop)` in `core/sources.py`, and for the same reason:
the signal is presence derived from file mtimes, not parsed work artifacts. It
belongs in `ATTENDED_SOURCES` (a human is at the keyboard) but must not be
promoted to `direct_work_evidence` while its only proof of duration is a
sampled mtime. See `docs/specs/source-evidence-policy.md`.

---

## Backlog

### FRAMER-1 — Detect Framer and tell the truth in `doctor`

- priority: **now**
- problem: Framer users get an empty report with no explanation. Gittan cannot
  say whether it looked, found nothing, or cannot look.
- user value: An honest answer to "does Gittan support Framer?" — including the
  part that is a limitation, surfaced where users already look for source health.
- non-goals: No events, no hours, no classification. This item deliberately
  ships **zero** contributed time.
- behavior: Detection of the Framer app-support root and its partition, wired
  into `collector_status` and the `doctor` source rows, with a reason string
  that names the retention limit rather than implying "not found".

```gherkin
Feature: Framer source visibility
  Gittan states what it can and cannot observe about Framer.

  Scenario: Framer is installed and doctor explains the retention limit
    Given the Framer application support directory exists
    When the user runs "gittan doctor"
    Then a Framer row is shown as detected
    And the reason states that Framer evidence is captured live and cannot be backfilled
    And no Framer hours are added to any report

  Scenario: Framer is not installed
    Given no Framer application support directory exists
    When the user runs "gittan doctor"
    Then the Framer row reads as not found
    And no warning is raised
```

- acceptance:
  - `gittan doctor` shows a Framer row in both states (installed / not installed).
  - The installed-state reason names the live-capture limitation explicitly.
  - `collector_status` carries the Framer entry with an event count of `0`.
  - No change to observed, billable, or truth-payload totals.
- validation: fixture-backed tests for both detection states (an installed
  tree and an empty home), plus `bash scripts/run_autotests.sh` green. Follow
  the collector + fixture contract in the `gittan-source-collector` skill.
- dependencies: none. This is the one item with no blocking decision.

---

### FRAMER-2 — Framer presence spans via `gittan capture`

- priority: **next**
- problem: The only way to ever have Framer time is to record it while Framer is
  open. Nothing does that today.
- user value: Framer afternoons stop vanishing. Time captured today remains
  reportable next month, because it lands in the append-only ledger.
- non-goals: No parsing of design content. No chat titles. No project names from
  Framer. No claim of billable direct work evidence.
- behavior: A capture-side Framer reader — a new key in
  `CAPTURE_SOURCES` (`core/session_capture.py`) — samples mtimes across the
  Framer partition (OPFS, Local Storage, IndexedDB) and writes presence spans
  through `core.evidence_store.capture_events`, tagged with the device, using
  the existing hash-chained, idempotent append path. Same technique already used
  for `Lovable (desktop)` ("Chromium cache-mtime on the operator's machine",
  `core/sources.py`).

```gherkin
Feature: Framer presence capture
  Framer activity is recorded as it happens, because it cannot be recovered later.

  Scenario: Capture records a Framer presence span
    Given Framer has written to its partition within the capture window
    When "gittan capture --source framer" runs
    Then a Framer presence record is appended to the evidence ledger
    And the record carries the device name and the passive_context role
    And running the same capture again appends no duplicate record

  Scenario: A report reads captured Framer evidence, not live state
    Given Framer presence records exist in the ledger for a past date
    And Framer has since rewritten its live local state
    When the user reports on that past date
    Then the captured Framer presence is still available as evidence

  Scenario: Framer presence alone does not manufacture billable hours
    Given a Framer presence span exists with no corroborating evidence
    When Gittan builds the report
    Then the span may appear as observed context
    But it must not be promoted into billable or approved invoice time
```

- acceptance:
  - `gittan capture --source framer` appends records; a second run is a no-op
    (fingerprint idempotency preserved).
  - Records survive a subsequent rewrite of Framer's live local state — proven by
    a test that mutates the fixture between capture and report.
  - Framer spans never raise billable totals on their own.
  - Gaps between samples are represented honestly as gaps, not interpolated into
    one continuous session.
- validation: fixture tests covering capture → mutate source → replay from
  ledger; idempotency test; a billable-total assertion. `run_autotests.sh` green.
- dependencies:
  - **Open decision — capture cadence.** `gittan capture` is invoked manually or
    by a timer/hook (`--if-enabled` exists for exactly this). There is no daemon.
    Framer coverage is a direct function of sampling frequency, so this item is
    not startable until the cadence mechanism is decided (launchd timer vs hook
    vs explicit user-run) and the resulting coverage claim is written down. A
    once-a-day capture would produce misleadingly thin Framer coverage.
  - FRAMER-1 (detection) should land first so `doctor` can report capture health.

---

### FRAMER-3 — Project attribution from stable Framer ids

- priority: **later**
- problem: A Framer presence span with no project is time Gittan found but cannot
  attribute — it lands in `Uncategorized` and helps nobody invoice.
- user value: Framer hours attach to the right project and customer.
- non-goals: **Never** the agent-chat `title` field. See FRAMER-6.
- behavior: Attribution keyed on the stable identifiers observed in the probe —
  `crdt-tree-version:<projectId>` (per design document) and `framer-recent-spaces`
  (workspace UUIDs) — mapped to projects through explicit user configuration in
  `timelog_projects.json`, in the same spirit as `project_id` owning identity
  elsewhere in the product.
- acceptance: a Framer id maps to a project only via explicit configuration; an
  unmapped id classifies as `Uncategorized` rather than guessing; the mapping is
  visible in `doctor`.
- validation: classification tests over fixture ids, including the unmapped case.
- dependencies: **blocked on GH-354** (research spike: local evidence shapes for
  display vs durable identity). That spike decides which live-state fields may
  become durable identity; Framer's ids are the same class of question. Do not
  pre-empt it.

---

### FRAMER-4 — Framer (web) derived from Chrome

- priority: **later**
- problem: Users who work in Framer in the browser rather than the desktop app
  get nothing at all.
- user value: Coverage for browser-first Framer users, at low cost.
- behavior: A derived source in the established pattern of `WordPress` and
  `Lovable (web)` — recognized from Chrome history against `framer.com` project
  URLs, `passive_context`.
- acceptance: `framer.com` project visits surface under a `Framer (web)` source;
  auth, login, marketing, and community URLs are excluded as noise.
- validation: Chrome fixture tests including the noise-exclusion cases.
- dependencies: none technically — it is deliberately `later` because the probe
  measured its ceiling: **23 visits over 2 days in ~7 weeks, almost all auth**.
  For desktop-app users this source is close to worthless, so it should not be
  built as if it were the answer to Framer coverage. Promote it when a
  browser-first Framer user actually appears.

---

### FRAMER-5 — Detect what has been published in Framer

- priority: **do not build yet**
- problem: Publishing is the delivery milestone a client recognizes — the natural
  narrative line in an invoice ("site published 12 Aug").
- why not yet: The probe found **no local trace whatsoever** — no publish tokens,
  no cached API responses, no publish event in Framer's own telemetry vocabulary.
  Publish state is server-side only. Building this means either:
  1. **Framer API + account auth** — a network, opt-in `delivery_evidence` source
     in the same class as GitHub, with its own consent, credential handling, and
     doctor surface. That is a separate spec, not a slice of this one; or
  2. **Polling the published URL over HTTP** — which yields no attribution, no
     duration, and no proof of who worked. It is not evidence.
- non-goal for now: do not let publish detection sneak in as a side effect of
  the collector work above. It is a different source class with a different
  consent story.
- promotion trigger: a decision to add network-backed delivery sources beyond
  GitHub, at which point this gets its own spec and its own issue.

---

### FRAMER-6 — Framer agent-chat titles as project identity

- priority: **do not build yet**
- why not: The Framer `keyval` store exposes a `title` next to `scopeId` and
  `lastMessageTimestamp`, and it is the most tempting field in the whole probe.
  Promoting a live chat title to hours identity is an **existing do-not-build
  rule**, stated in `core/session_capture.py` and owned by GH-354. Framer must
  not be the exception that quietly reverses it.
- promotion trigger: GH-354 concludes and explicitly permits it.

---

### FRAMER-7 — Reading Framer's telemetry queue as an event log

- priority: **do not build yet**
- why not: `framer-tracking-client-queue` looks like an activity log and is not
  one. It is a drain-on-send buffer; the only entries the probe found were stuck
  events from roughly seven months earlier that had failed to upload. A collector
  reading it would report a burst of "activity" on a day nothing happened, and
  silently miss every day the queue drained normally. It is worse than no signal
  because it is confidently wrong.

---

## Summary of priorities

| Item | Priority | Blocked by |
| --- | --- | --- |
| FRAMER-1 Detection + honest `doctor` row | **now** | — |
| FRAMER-2 Presence spans via `capture` | **next** | capture-cadence decision; FRAMER-1 |
| FRAMER-3 Attribution from stable ids | later | GH-354 |
| FRAMER-4 Framer (web) from Chrome | later | demand (measured ceiling is low) |
| FRAMER-5 Publish detection | do not build yet | needs a network delivery-source spec |
| FRAMER-6 Chat title as identity | do not build yet | GH-354 do-not-build rule |
| FRAMER-7 Telemetry queue as log | do not build yet | never — signal is misleading |

## Open decisions to resolve before FRAMER-2

1. **Capture cadence.** Timer, hook, or explicit user run? This sets Framer's
   real coverage and therefore what the product may claim.
2. **Coverage honesty.** How does a report show that Framer time exists only from
   the day capture was switched on? Silence here re-creates the "Gittan missed my
   time" complaint in a new place.
3. **Role confirmation.** `passive_context` + attended is proposed above. Confirm
   before implementation, since it determines whether Framer spans can ever lead
   a session label.

## Non-goals for the whole story

- No network calls to Framer in any `now`/`next` item; local-first only.
- No writes to any Framer file. Read-only, WAL-safe, as with every other source.
- No Framer content (design nodes, chat text, page copy) enters evidence — the
  detail line is presence and provenance, nothing more.
- No promotion of Framer evidence into approved invoice time by any path.
