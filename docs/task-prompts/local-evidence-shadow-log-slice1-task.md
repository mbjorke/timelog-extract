# Local Evidence Shadow Log — Slice 1 (measure-first foundation)

Spec: `docs/specs/local-evidence-shadow-log.md` (rests on
`docs/specs/timelog-truth-standard-rfc.md`). Source roles: `docs/specs/source-evidence-policy.md`.

## Context

Discovering [GitButler](https://github.com/gitbutlerapp/gitbutler) re-surfaced a
standing worry: Gittan is a **stateless re-aggregator**. `collect_all_events()`
reads sources at report time, `aggregate_report()` computes sessions, and
nothing is persisted in Gittan's own format. GitButler's value is partly
architectural — it owns its operation log and treats git state as a projection.
The shadow log is Gittan's equivalent: an own, durable evidence store so source
log rotation, cache resets, and vendor retention limits cannot erase evidence
for work that actually happened.

The **record contract** — not the storage engine — is the asset that prevents
painting ourselves into a corner. Get the contract right and the physical store
(JSONL today, SQLite/DuckDB later) is a swap, not a rewrite.

Open volume question: current collectors emit **report-level** events (hundreds
per day). A more granular capture layer (keystroke/edit/oplog style) could reach
**millions per day**. The spec deliberately stores *normalized* evidence, not
"unlimited raw source dumps", and the vision is explicitly **not** "track
everything" software. We do not yet know the durable record rate — so this slice
is **measure-first**: lock the contract, measure real volume, then choose the
engine on data.

Decided storage direction (pending the measurement gate):

- **Not** pg_duckdb or any server-based store — a running Postgres server breaks
  local-first; explicit non-goal.
- JSONL-first append-only under `~/.gittan/evidence/` **if** the measured
  durable rate is small; tiered append → columnar Parquet + **embedded** DuckDB
  if it is large. Embedded DuckDB can later read JSONL/Parquet directly as a
  read layer regardless of which is chosen.

## Backlog (product-owner)

### 1. Evidence record contract (engine-agnostic foundation)

- **priority:** `now`
- **problem:** Without a locked, versioned record contract, every storage engine
  becomes a dead end. This is the anti-corner asset and the precondition for
  measuring normalized record size.
- **user value:** Guarantees JSONL today and SQLite/DuckDB tomorrow read the
  *same* events without migration; an invoice can trace to an immutable record.
- **non-goals:** No physical writes here (item 2 measures, item 3 persists); no
  redaction (later); no retention decision (later).
- **behavior:** Define an `EvidenceRecord` contract with: `schema_version`,
  `fingerprint`, `source`, `source_provenance`, `observed_at`, `captured_at`,
  `detail` (normalized), `project_at_capture`, `source_role` (from
  source-evidence-policy), `content_hash`, `prev_hash`.
- **key decision (locked here):** `fingerprint` is computed on the *immutable
  observation* — `source` + UTC-normalized `observed_at` + `detail` — and
  **excludes** `project`. `project_at_capture` is stored as mutable metadata.
  Otherwise reclassification fabricates "new" events and dedup breaks. This
  reuses the `core/events.py::event_key()` tuple but drops the project field.
- **acceptance:**
  - Contract documented with field names, types, and `schema_version = 1`.
  - Fingerprint algorithm is deterministic and specified (hash over `source` +
    UTC `observed_at` + `detail`).
  - Hash chain specified: `content_hash = H(record without prev_hash)`;
    `prev_hash` = previous record's `content_hash`.
- **validation:** Contract test locking field set + fingerprint determinism
  (`tests/test_evidence_shadow_log.py`): same observation twice → identical
  fingerprint; differing `project_at_capture` does not change the fingerprint.
- **dependencies:** none (builds on existing event dict shape and `event_key`).

```gherkin
Scenario: Fingerprint is stable and independent of project classification
  Given the same observed event is collected twice
  And the project classification differs between runs
  When the fingerprint is computed
  Then the fingerprint should be identical both times
  And project_at_capture may differ without creating a new record
```

### 2. Volume & footprint measurement spike

- **priority:** `now`
- **problem:** We do not know whether the durable store is 10^4 or 10^7
  records/day — and that decides the engine. Guessing either way paints us in.
- **user value:** A data-backed engine decision instead of a guess; guards
  against both over-engineering (pg_duckdb for nothing) and under-sizing (JSONL
  that will not scale).
- **non-goals:** **No durable store is established here** — no
  `~/.gittan/evidence/`, no opt-in durable write, no retention. The spike is
  read-only and ephemeral (writes only a measurement report under `out/`). No
  new privacy surface.
- **behavior:** A measurement script (under `scripts/`, not `core/`) runs the
  existing collectors plus an optional granular candidate collector and measures,
  per source: raw observation rate/day; rate **after** normalization +
  fingerprint dedup; fingerprint cardinality (does the dedup index fit in
  memory?); bytes/day and projected 1-year footprint under JSONL / SQLite /
  Parquet+DuckDB.
- **decision gate (the important output):** the report recommends an engine
  against a threshold — e.g. durable normalized rate ≤ ~10^5/day & small
  footprint → **JSONL-first**; ≥ ~10^6/day or multi-GB/year → **tiered append →
  Parquet + embedded DuckDB**.
- **acceptance:**
  - The script runs without creating any durable store.
  - The report contains raw rate, post-dedup rate, fingerprint cardinality, and
    footprint projection per engine.
  - The report ends with an explicit engine recommendation and the threshold
    that triggered it.
- **validation:** Run against fixtures + one real machine-day; artifact under
  `out/` (benchmark-style, consistent with the truth-RFC artifact culture). Test
  locking the report's key fields.
- **dependencies:** item 1 (to measure normalized record size).

```gherkin
Scenario: Measurement spike recommends an engine without creating a durable store
  Given the measurement spike runs against current sources
  When it measures raw and post-dedup rates and footprint
  Then it should write a measurement report with an explicit engine recommendation
  And no ~/.gittan/evidence/ directory should have been created
```

### 3. Durable capture — engine chosen by the measurement

- **priority:** `next` (gated on item 2)
- **behavior:** Either opt-in JSONL append-only **or** tiered append →
  Parquet + DuckDB, depending on the spike. Behind an opt-in flag (proposed
  `--shadow-log on|off` + config key, mirroring `--calendar-source on`). Capture
  runs **only when a report/status command runs** — no hidden background job.
  Off by default: without the flag, no directory/file is created and reports are
  unchanged. Idempotent dedup on fingerprint. Hash chain is per-record (JSONL) or
  per-segment (tiered). New module `core/evidence_store.py` (keep under 500
  lines). `~/.gittan/evidence/` is gitignored and treated as `TIMELOG.md`-class
  sensitive data.

```gherkin
Scenario: New events are appended when shadow logging is on
  Given shadow logging is enabled
  And a collector returns a new event for today
  When Gittan runs a report
  Then the event should be appended to the shadow log
  And the record should include source, observed_at, captured_at, fingerprint, and prev_hash

Scenario: Duplicate events do not create duplicate records
  Given shadow logging is enabled
  And the same source event is collected twice
  When Gittan runs reports both times
  Then only one record should exist for that fingerprint

Scenario: Off by default
  Given shadow logging is not enabled
  When the user runs a normal report
  Then no durable evidence store should be created
  And the report should complete from live sources as usual
```

### 4. Replay from the shadow log for closed windows

- **priority:** `next` (after item 3)
- **behavior:** For closed windows, the report can read events from the shadow
  log and mark them "from shadow log", even after the source rotated. Ties to the
  truth-RFC "frozen inputs / deterministic replay" line.

```gherkin
Scenario: Report uses shadow evidence after upstream cleanup
  Given the shadow log captured events for a closed date window
  And the original source log has been removed
  When the user runs a report using retained evidence
  Then Gittan should include the retained events
  And the output should say the evidence came from the shadow log
```

### 5. Health-monitor surface

- **priority:** `next` (after item 3)
- **behavior:** `doctor`/status shows: on/off, last capture, records today, chain
  integrity (OK/broken), sources with live evidence but no retention. No raw
  event details exposed. A tampered record (broken `prev_hash`) is flagged as a
  chain break. Ties to `docs/specs/timelog-health-monitor.md` and the existing
  `core/cache_evidence_health.py`/doctor pattern.

### Later

- Retention policy + compaction (`retention-policy.json`, window); slice 1 keeps
  everything, no deletion.
- Redaction by default (raw detail opt-in / recoverable from live source while
  available) — required by the privacy baseline before broad rollout.
- Export / deletion controls (user-owned data must be exportable and erasable).
- The non-chosen engine as a query layer (DuckDB can read JSONL/Parquet either
  way).

### Do not build yet

- Background daemon / launch agent for capture — open question in the spec;
  conflicts with "no hidden background collection" and "not a surveillance
  product"; needs clear consent UX first.
- pg_duckdb or any server-based storage — breaks local-first; explicit non-goal.
- Treating shadow evidence as approved invoice truth — explicit spec non-goal;
  observed/classified/approved stay separate.
- A durable granular firehose before the measurement spike has reported.

## Open decisions before build (beyond the fingerprint decision in item 1)

1. Flag surface: `--shadow-log on|off` + config key (recommended — mirrors
   `--calendar-source on`).
2. Starting `schema_version`: proposed `1`, parallel to `TRUTH_PAYLOAD_VERSION`.
3. Detail default: store normalized detail as-is in slice 1 (local + opt-in),
   defer redaction to Later — documented clearly.
4. Engine-selection thresholds for item 2's decision gate (calibrate from the
   first measurement run).

## First PR

Items 1 + 2 together (contract + measurement spike) — locks the foundation and
yields data to choose the engine, without establishing any durable store early.

## Traceability

- story_id: `GH-151` (https://github.com/mbjorke/timelog-extract/issues/151)
- spec_status: `draft`
- implementation_status: `not built`
- created_at: 2026-06-18
- last_updated_at: 2026-06-18
- implementation.pr: pending
- implementation.branch: claude/gitbutler-inspiration-4nkcrm
- implementation.commits: []
- validation.evidence: pending
- validation.decision: NO-GO
- changelog:
  - 2026-06-18: Initial product-owner pass. Measure-first slice for the local
    evidence shadow log, prompted by GitButler architecture inspiration. Locked
    the engine-agnostic record contract, fingerprint-excludes-project decision,
    and JSONL-first-vs-tiered storage fork gated on a volume measurement spike.
  - 2026-06-18: Filed tracking issue GH-151; story_id set.
