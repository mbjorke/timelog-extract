# Task Story: Framer As A Gittan Source

Product-owner planning pass for adding the Framer design tool as a Gittan
source. This is a **backlog**, not an implementation. It is grounded in a live
probe of a real Framer install (see *Evidence probe* below), because the
feasibility of this source turns entirely on what Framer actually retains
locally — and the answer changes the shape of the work.

## Traceability

- story_id: `GH-561`
- priority: `later` (demoted from `now` on 2026-08-18 — see *Priority review*)
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
  - `2026-08-18: Added canvas-edit probe; corrected the over-claimed "no retention" finding; made an idle control a prerequisite for FRAMER-2.`

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
| AI agent chat state | `IndexedDB/…framer.com…leveldb`, `keyval` store: `activeChatAgentId`, `scopeId`, `title`, `lastMessageTimestamp` | 579 decoded `lastMessageTimestamp` values spanned **4 minutes of a single day**. Note the confound: the probe user had not opened Framer in months, so a single-day span is equally consistent with an append-only store holding one short session. Treat "no history" as **unproven** for this store. |
| Design-document state | Local Storage `crdt-tree-version:<projectId>`, `framer-recent-spaces` (workspace UUIDs), `VekterUserDefaults` | **Version counters and id lists, no timestamps.** Tells you the document changed since the last sample; never when or how much. |
| OPFS / CRDT files | `Partitions/framer/File System/…` | 13 files, **all mtimes on the probe day**. Coarse "the app wrote something" signal, not retroactive. |
| Framer's own telemetry | Local Storage `framer-tracking-client-queue` | **Drain-on-send buffer.** Observed vocabulary: `app_foreground`, `app_background`, `ui_long_frame`, `error_toast`, `code_generation`, `agent_update_project_tool`. The only retained entries were **stuck events from ~7 months earlier** that failed to send. Not a log. |
| Chrome history | Chrome `Default/History` | **23 visits over 2 distinct days in ~7 weeks**, mostly `api.framer.com/auth`, `/login`, `/welcome`. Real work happens in the app, not the browser. |
| Publish / deploy state | cache, Local Storage, IndexedDB | **Nothing.** Zero publish/deploy/`framer.website`/custom-domain tokens; no cached `api.framer.com` responses; no publish event in the telemetry vocabulary. |

### The two conclusions that shape this backlog

1. **Framer evidence is not backfillable — but for a narrower reason than
   "it rewrites everything".** The Framer profile persists for *years*: Local
   Storage values span `2024-11-30 → 2025-11-11` inside a file last written in
   January. What does not exist is any component that stores a **work log**.
   Version counters, id lists and live agent state persist happily; elapsed
   working time is never recorded, so it cannot be reconstructed after the fact.
   `gittan report --last-month` can never recover Framer time that was not
   captured while it happened. This is the retention gap
   `docs/specs/local-evidence-shadow-log.md` was written for, and Framer is the
   first source where the shadow log is not an improvement but a
   **precondition**.
2. **Publishing is not locally observable.** Publish state lives server-side.
   Detecting it means a network call to the Framer API with account auth — a
   different class of source (opt-in, `delivery_evidence`, like GitHub), not a
   variation on the collector below.

### Canvas-edit probe (2026-08-18, live experiment)

The question "can Gittan see *regular* design work — moving layers, resizing
frames — rather than only AI chat?" was tested directly: the Framer partition was
sampled every 3 seconds for 3.4 minutes while the user performed real canvas
edits in the running app.

**Result: edits are visible, but not as edits.**

| Writer | Frequency during editing | What it actually is |
| --- | --- | --- |
| `sentry/scope_v3.json` | 10× (9 B total) | crash-reporter scope |
| Local Storage `…/000783.log` | 8× (1.4 KB) | tracking queue / prefs |
| Session Storage `…/010383.log` | 7× (518 B) | session housekeeping |
| `WebStorage/QuotaManager-journal` | 6× (60 KB) | storage bookkeeping |
| Cookies, Network state, DIPS | 2–3× each | network housekeeping |
| **OPFS CRDT document** `File System/000/t/00/…` | **1×** (+13.4 MB) | **the design document itself** |
| IndexedDB `…/000164.log` | **1×** (+2.8 KB) | doc/agent state flush |

The inversion is the finding: **the files that change often are not design work,
and the file that is design work changes rarely.** The high-frequency writers are
app-lifecycle and telemetry housekeeping — they say "Framer is open and running",
not "a layer moved". The one genuinely edit-correlated artifact, the OPFS CRDT
document, flushed **once in 3.4 minutes of continuous editing** on a
save/checkpoint cadence, and it flushes identically for AI-generated changes.

Consequences for what Gittan may claim:

- **Presence is measurable at good resolution.** A dense heartbeat of writes
  exists whenever the app is running.
- **"Design work" is not separable.** Nothing on disk distinguishes dragging
  layers from the AI agent generating, from the app merely sitting open. Gittan
  can honestly report *time in Framer*, never *time designing in Framer*.
- **Edit-count metrics are not available.** One CRDT flush per multi-minute chunk
  cannot support "N edits" or intensity weighting.

### Idle control (2026-08-18) — active and idle are separable

The idle control was run: Framer left open and untouched, identical scope, 3s
cadence, same 210s duration as the active window.

| | Active (editing) | Idle (untouched) | Ratio |
| --- | --- | --- | --- |
| Ticks with any write | 34 | 17 | 2× |
| **Total bytes written** | **15,777,098** | **61,150** | **258×** |

**A naive heartbeat would bill idle time — an allowlisted one would not.** Writes
never stop while Framer runs, so "any file changed" is not a usable signal. But
the per-file split is clean:

| Writer | Active | Idle | Use |
| --- | --- | --- | --- |
| `Session Storage/…log` | 7× | **0×** | strongest discriminator |
| `sentry/scope_v3.json` | 10× | **0×** | discriminates, but it is a crash reporter — avoid depending on it |
| `Local Storage/…log` | 8× | 1× | supporting |
| `DIPS-wal` | 2× | 0× | supporting |
| `WebStorage/QuotaManager-journal` | 6× | **7×** | pure noise floor — must be ignored |
| `Cookies`, `Network Persistent State`, GPU/Dawn caches | 1–3× | 1–3× | pure noise floor — must be ignored |

So the active/idle threshold that FRAMER-2 needed **exists and is measured**:
write *volume* (two orders of magnitude apart) combined with an allowlist of
Session Storage / Local Storage activity, and an explicit denylist for the
housekeeping writers that tick regardless.

Caveats to carry into implementation, not to gloss over:

- One 3.5-minute window per condition. A longer idle run may eventually tick
  Session Storage on some periodic cadence; validate against a 30-minute idle
  before shipping a threshold.
- The `Code Cache/wasm` and `Cache_Data` entries that appear active-only are
  almost certainly one-time lazy loads from that session, not a repeatable
  per-edit signal. Do not build on them.
- The idle window had the app open on screen. Whether a **backgrounded** Framer
  looks like idle or like nothing is not yet measured.

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

- priority: **later** (was `now`; demoted 2026-08-18 — see *Priority review*)
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

- priority: **later** (was `next`; demoted 2026-08-18 — see *Priority review*)
- problem: The only way to ever have Framer time is to record it while Framer is
  open. Nothing does that today.
- user value: Framer afternoons stop vanishing. Time captured today remains
  reportable next month, because it lands in the append-only ledger.
- non-goals: No parsing of design content. No chat titles. No project names from
  Framer. No claim of billable direct work evidence. **No claim that the span is
  "design work"** — the canvas-edit probe showed on-disk signals cannot separate
  dragging layers from AI generation or from an idle open app. The user-facing
  wording is *time in Framer*.
- behavior: A capture-side Framer reader — a new key in
  `CAPTURE_SOURCES` (`core/session_capture.py`) — samples mtimes across an
  **allowlist** of the writers the idle control showed actually discriminate
  (Session Storage, and the Local Storage log), and writes presence spans
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
  - **Idle does not bill.** With Framer open and untouched, the collector must not
    produce a growing presence span. The idle-control measurement defines the
    threshold that makes this true; if no on-disk signal separates idle from
    active, the item is re-scoped rather than shipped with idle counted as work.
- validation: fixture tests covering capture → mutate source → replay from
  ledger; idempotency test; a billable-total assertion; a fixture derived from the
  **idle control** proving an untouched app yields no span. `run_autotests.sh` green.
- dependencies:
  - **Open decision — capture cadence.** `gittan capture` is invoked manually or
    by a timer/hook (`--if-enabled` exists for exactly this). There is no daemon.
    Framer coverage is a direct function of sampling frequency, so this item is
    not startable until the cadence mechanism is decided (launchd timer vs hook
    vs explicit user-run) and the resulting coverage claim is written down. A
    once-a-day capture would produce misleadingly thin Framer coverage.
  - **Idle-control measurement** — first run done 2026-08-18 (see *Idle control*
    above): 258× write-volume separation plus a Session Storage allowlist. Two
    runs remain before the threshold can be shipped against — a 30-minute idle
    and a backgrounded app — and until they pass, *Idle does not bill* cannot be
    accepted.
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

## Priority review (2026-08-18) — demoted `now` → `later`

The first pass set FRAMER-1 to `now` on the strength of the evidence work being
done. That conflated *"we understand this source"* with *"this source should be
built next"*. Re-read against the open backlog, it should not be.

**What FRAMER-1 actually delivers:** a `doctor` row, and zero reported hours by
its own design. It is a documented limitation, not a capability.

**What it is competing with,** all currently `now`:

| Issue | Why it outranks a new source |
| --- | --- |
| GH-431 | ~22 client-name leaks already committed to a **public** repo — live exposure, not a future risk |
| GH-515 | The control that stops new client data reaching issues and PRs |
| GH-544 | Hours silently move to another project — and often another **customer** — when a Cursor conversation continues in a different workspace. Wrong-customer billing is the worst defect class this product has |
| GH-550 | Follow-ups from the post-merge review of the data-directory hook guard |

Every one of those is about hours already being wrong, or client data already
being exposed, for sources people use daily.

*Reconciled later the same day:* an agent swarm merged five fixes (GH-448, GH-521,
GH-549 closed cleanly; GH-544 and GH-414 have merged fixes but stayed open, and
GH-414 moved to `next`). The `now` band is therefore thinner than when this review
was written — but the demotion does not rest on the length of that list. It rests
on Framer's own properties: no demand signal, a zero-hours first slice, and a
successor blocked on a decision that is not Framer's to make. GH-431 was
re-verified against the repo's own guard and is genuinely still open work. Framer is a source with **no demand
signal**: no issue existed for it before this spec, no beta tester has asked, and
its first slice adds no hours to any report.

**Demand evidence is weak in the probe itself.** The install that motivated this
work had not been opened in months before the probe day, and Chrome history shows
23 Framer visits across 2 days in ~7 weeks. That is an experiment, not a workflow.

**The second slice is blocked anyway.** FRAMER-2 cannot start until the
capture-cadence question is answered, and that question is bigger than Framer —
it decides how *any* sampled source works. Building FRAMER-1 now would park a
zero-hours `doctor` row in the tree while its only useful successor waits.

### What today's work is genuinely worth

The measurements do not go stale with the demotion, and their value is mostly
**not** Framer-specific. The idle control established a reusable technique for
*any* Electron-based tool: a write-volume separation of two orders of magnitude
plus an allowlist of discriminating writers, with the housekeeping noise floor
named explicitly. That is direct evidence for **GH-327** (attendance taxonomy:
presence ≠ active authorship for cache-mtime sources), which is already `next` and
which governs Lovable (desktop) — a source that ships today and is used more than
Framer.

So the durable output of this pass is a measurement banked against GH-327, not a
collector. Framer becomes the worked example that proves the technique.

### Promotion trigger

Promote FRAMER-1/FRAMER-2 back to `next` when **either**:

1. a real user (beta tester or the maintainer's own sustained use) actually works
   in Framer across multiple weeks, so the source has a workflow behind it; **or**
2. the capture-cadence decision lands for other reasons, making FRAMER-2 a small
   increment on infrastructure that already exists rather than its justification.

Nothing in this spec needs re-derivation when that happens — the evidence,
thresholds and traps are recorded above.

---

## Summary of priorities

| Item | Priority | Blocked by |
| --- | --- | --- |
| FRAMER-1 Detection + honest `doctor` row | ~~now~~ → **later** | demand signal (see *Priority review*) |
| FRAMER-2 Presence spans via `capture` | ~~next~~ → **later** | capture-cadence decision; FRAMER-1 |
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
4. **Idle vs active threshold — measured, not yet validated.** One 3.5-minute
   control showed idle and active separable by two orders of magnitude of write
   volume, with Session Storage writing 7× when active and 0× when idle. That is
   enough to design against, and not enough to ship on: a 30-minute idle run may
   still expose a periodic writer, and a backgrounded Framer is unmeasured. Both
   runs are prerequisites of FRAMER-2's *Idle does not bill* acceptance, so this
   decision stays open until they pass. FRAMER-2 therefore has two blockers, not
   one: this, and the capture-cadence decision (1).

## Non-goals for the whole story

- No network calls to Framer in any `now`/`next` item; local-first only.
- No writes to any Framer file. Read-only, WAL-safe, as with every other source.
- No Framer content (design nodes, chat text, page copy) enters evidence — the
  detail line is presence and provenance, nothing more.
- No promotion of Framer evidence into approved invoice time by any path.
