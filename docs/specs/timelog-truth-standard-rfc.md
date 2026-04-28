# RFC: Timelog Truth Standard

Status: Draft
Owner: Maintainer + AI agents

## Why this RFC

Current reporting is useful but heuristic-heavy. For a world-standard ambition, we
need a model that is reproducible, auditable, and measurable against explicit
"truth" references, not just plausible classification.

## Executive summary

- Determinism is mandatory: same frozen inputs + same policy package MUST produce
the same normalized payload hash.
- Reporting output is split and explicit: observed, classified, and approved
invoice time are never conflated.
- Compliance requires evidence completeness (100% session evidence payload),
reproducibility metadata, and deterministic replay artifacts.
- Validation scope is annual and all-project: every month and every active project
must be included or explicitly excluded with reason codes.
- Release decision is gate-driven (`GO` / `conditional GO` / `NO-GO`) with strict
waiver limits (no determinism waiver on closed-window replay).

## Decision status snapshot


| Area                                      | Status              | Notes                                                                                     |
| ----------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------- |
| Determinism gate on closed window         | Locked              | MUST pass; no waiver allowed                                                              |
| Evidence payload completeness             | Locked              | 100% session coverage required                                                            |
| Annual + all-project benchmark protocol   | Draft (operational) | Protocol and artifacts defined; tune thresholds via first cycle                           |
| Numeric gate thresholds                   | Draft               | Initial values set; calibrate after first benchmark cycle                                 |
| Active project threshold values           | Draft               | v1 values defined; finalize after initial annual run                                      |
| Volatile field allowlist scope            | Open                | Final allowlist governance still pending                                                  |
| Conditional GO for main/release promotion | Locked              | Not allowed without explicit maintainer risk acceptance; never for release promotion tags |


## Reader map

Use this order for fastest understanding:

1. `Executive summary` + `Decision status snapshot` (policy intent),
2. `Determinism requirements` + `Run-level reproducibility contract` (hard rules),
3. `Evaluation framework` + `Release gates` (how policy is measured),
4. `Implementation slices` + `Artifact format` (how to build and verify).

## Problem statement

- Classification currently depends on mutable keyword/url rules.
- Small rule changes can move hours significantly between projects/customers.
- "Tracked time" and "invoice truth" are often conflated in user expectations.
- We lack a formal confidence model and public benchmark process.

## Objective

Define a standard that makes each reported hour:

- reproducible from versioned inputs and rules,
- explainable with evidence,
- calibratable against a known ground truth,
- auditable over time.

## Scope

In scope:

- evidence model for sessions/events,
- confidence and decision policy,
- benchmark/evaluation workflow,
- versioned output contract for external consumers.

Out of scope (v1):

- perfect automatic billing decisions,
- legal/compliance claims beyond transparent evidence,
- mandatory cloud inference.

## Non-goals and anti-patterns

The following are explicitly out-of-policy for Timelog Truth Standard
implementation:

- claiming determinism while using open-window replay that includes active,
changing data without snapshot freeze,
- silently changing classification behavior without policy package version bumps,
- treating classified time as invoice-approved time by default,
- suppressing drift/determinism failures to keep release velocity,
- using undocumented volatile fields in deterministic hash comparison logic,
- relying on manual memory or narrative-only explanations where machine evidence
payload is required.

## Terminology

- **Observed time**: activity inferred from data sources (browser, IDE, mail, git).
- **Classified time**: observed time mapped to project/customer by rules/model.
- **Invoice time**: human-approved billable time for invoicing.
- **Truth set**: labeled reference data used to evaluate the classifier.

## Normative language

This RFC uses the following requirement levels:

- **MUST**: required for compliance with Timelog Truth Standard.
- **SHOULD**: strongly recommended; deviations require explicit rationale.
- **MAY**: optional behavior that does not break compliance.

## Principles

1. **Determinism first**: same inputs + same rule/model version => same result.
2. **Evidence over guessing**: each classified session includes reason codes.
3. **Human authority**: invoice decisions remain explicit until confidence is proven.
4. **Version everything**: config, model behavior, output schema, evaluation set.

## Determinism requirements (v1)

Determinism is a hard requirement, not a best effort.

For any run claiming Timelog Truth Standard compliance, all items below MUST be
true:

1. **Frozen inputs**
  - source snapshots are immutable for the run window,
  - event collection range is explicit (`from`, `to`, timezone),
  - no hidden "now" dependency after snapshot time is fixed.
2. **Stable normalization**
  - timestamps normalized to a single canonical timezone representation,
  - event IDs derived from stable fields only,
  - duplicate collapse rules are deterministic and versioned.
3. **Stable ordering**
  - events sorted by deterministic key before sessionization,
  - tie-breakers are explicit (timestamp, source, stable event id),
  - no reliance on filesystem iteration order.
4. **Stable math**
  - session boundary, rounding, and minimum-session rules are fixed per version,
  - float handling uses explicit rounding policy before output boundaries.
5. **Stable policy**
  - confidence weights/thresholds are versioned and included in output metadata,
  - fallback behavior is explicit (no silent heuristic branch changes).

If one of these cannot be guaranteed, output MUST be marked
`determinism_status=degraded` with a machine-readable reason code.

## Proposed model

### 1) Session decision classes

- `work` (high confidence)
- `maybe` (requires review)
- `personal_or_unclear` (excluded by default from billing views)

### 2) Confidence score (0-1)

Derived from weighted evidence:

- strong project anchors (repo path, project-specific domain, issue keys),
- cross-source correlation (browser + git/IDE proximity),
- session continuity and dwell time,
- rule conflict penalties (multiple plausible projects),
- generic-term penalties.

### 3) Decision policy

- auto-include only above high-confidence threshold,
- put medium-confidence sessions in review queue,
- exclude low-confidence sessions by default.

Thresholds are configurable and versioned.

## Evidence contract (per session)

Each session should carry:

- `decision_class`
- `confidence_score`
- `matched_evidence` (exact terms/urls/signals used)
- `negative_evidence` (conflicts/penalties)
- `rule_version`
- `input_fingerprint` (stable hash of contributing events)
- `determinism_status` (`ok` or `degraded`)
- `determinism_reasons` (empty when `ok`)

This enables reproducible audits and explanations.

## Run-level reproducibility contract

Every report payload MUST include a run-level reproducibility block:

- `input_snapshot_id` (or equivalent immutable source manifest hash),
- `policy_version` (rules + thresholds + scoring mode),
- `schema_version`,
- `timezone_basis`,
- `determinism_status`,
- `determinism_reasons`.

This makes "same run, same result" verifiable without reverse-engineering logs.

## Determinism validation procedure (draft)

For each benchmark month, run a deterministic replay check:

1. Collect and freeze the input snapshot manifest.
2. Run report generation with fixed policy/schema/timezone inputs.
3. Re-run the exact same command on the same snapshot.
4. Compare payloads after removing explicitly allowed volatile fields.

Precondition:

- replay checks must use a **closed** time window, or a formally frozen snapshot
cut taken at a fixed timestamp.
- windows that include actively changing "today" data are expected to drift and
must be treated as non-deterministic by design.

Expected outcome:

- payload hash A == payload hash B,
- `determinism_status=ok`,
- no unexplained key-level drift.

If hashes differ, the run is a determinism failure, not a soft warning.

### Initial local pilot (determinism replay)

A local replay pilot on a fixed historical day was executed with this flow:

1. run report to JSON (`run1`),
2. rerun same command to JSON (`run2`),
3. compare payloads after stripping volatile fields.

Observed outcome in the pilot: normalized payload equality passed
(`normalized_equal=True`).

This does not replace benchmark gating, but confirms the validation procedure is
practical to execute in day-to-day feature work.

### Full-year all-project replay pilot

Two full-year style replay pilots were executed:

1. **Open window pilot** (`2026-01-01` to `2026-04-26`, includes active day):
  - result: `normalized_equal=False` (expected drift from active data).
2. **Closed window pilot** (`2026-01-01` to `2026-04-25`, excludes active day):
  - result: `normalized_equal=True`.

Interpretation:

- determinism is achievable at year-scale when replay preconditions are respected
(closed window or frozen snapshot cut),
- open-window replay should be treated as a guardrail violation, not a benchmark
failure.

### Allowed volatile fields (initial draft)

These fields may differ between two equivalent runs and must be excluded from
the deterministic hash comparison:

- `generated_at` (or equivalent report generation timestamp),
- transient runtime telemetry fields not used for classification decisions.

All allowed volatile fields MUST be:

- explicitly listed in policy version docs,
- machine-excluded by deterministic hash tooling,
- absent from any billing/classification decision path.

## Policy package contract (versioned)

Every deterministic run must reference one immutable policy package.

Minimum policy package fields:

- `policy_version` (semantic version for behavior changes),
- `rule_bundle_sha` (hash of effective project/rule config),
- `scoring_profile` (weight set name + version),
- `threshold_profile` (work/maybe/personal thresholds + version),
- `volatile_field_allowlist_version`,
- `normalization_profile_version` (timestamp, dedupe, ordering rules).

Compatibility rule:

- any change affecting classification, confidence, or deterministic hashing must
bump at least one policy package version field.

## Deterministic hash profile (v1 draft)

Deterministic hash input should include:

- normalized session payloads,
- run-level reproducibility contract fields (except allowed volatile fields),
- policy package contract values.

Deterministic hash input should exclude:

- allowed volatile fields,
- local machine telemetry not used in decision logic.

## Evaluation framework

### Truth sets

- Build labeled monthly samples (multiple customers/projects patterns).
- Keep train/validation slices separate from exploratory tuning.

### Annual + all-project benchmark protocol (draft)

Each standard-candidate validation cycle must include:

1. **Full-year window set**
  - all calendar months in target year are represented,
  - each month validated with closed-window replay inputs.
2. **All-project inclusion**
  - every project with activity above agreed threshold is included in benchmark
   scoring or explicitly marked excluded with reason code.
3. **Cross-month consistency check**
  - run month-by-month and annual aggregate comparisons,
  - confirm no hidden policy drift between month runs and annual run.
4. **Evidence completeness sweep**
  - ensure 100% session evidence payload coverage across all included projects.

Required output artifacts:

- `benchmark_manifest.json`
- `benchmark_metrics.json`
- `determinism_replay_report.json`

See `Artifact format (minimum required keys)` for the canonical key contract.

### Core metrics

- project-level precision/recall/F1,
- customer-hour error (absolute + signed drift),
- false-positive rate on personal browsing,
- review load (% sessions in `maybe`),
- stability metric (delta after rule updates on unchanged input).
- determinism replay metric (same snapshot replay => 0 output drift).
- annual coverage metric (share of days/projects included in benchmark windows).

### Release gates (draft)

- no regression on precision beyond agreed threshold,
- customer-hour drift below gate for benchmark months,
- explainability coverage: 100% sessions have evidence payload.
- determinism gate: replaying the same frozen snapshot yields byte-identical
report payload (except explicitly allowed metadata fields like `generated_at`).

#### Draft numeric gates (for first operational cut)

- precision regression gate: `<= 1.0` percentage point drop vs prior approved
policy package on same benchmark set,
- customer-hour drift gate: absolute drift `<= 2.0%` per benchmark month and
signed drift near zero over annual aggregate,
- review-load gate: `maybe` bucket `<= 35%` of sessions in benchmark baseline,
- annual coverage gate: benchmark includes all months in target year and all
active projects with >= minimal activity threshold.

### Active project threshold (draft v1)

For annual coverage gate calculations, a project is considered **active** when it
meets at least one of:

- `>= 3` sessions in the target year, or
- `>= 2.0` classified hours in the target year, or
- explicitly flagged as business-critical in benchmark manifest metadata.

Projects below threshold MUST still be recorded, and MAY be marked
`coverage_exempt_below_threshold` with reason code.

### Determinism failure handling

When determinism gate fails:

1. block release promotion for that policy version,
2. emit a drift report with changed keys and first divergence point,
3. require either:
  - a fix restoring deterministic replay, or
  - an explicit policy-version bump + migration note explaining intentional
  non-deterministic change.

No silent acceptance of replay drift.

### Gate waiver policy (draft)

Waivers are exceptional and MUST NOT apply to determinism gate on closed windows.

Allowed waiver scope (MAY):

- non-determinism-independent quality gates (for example temporary review-load
spike) with documented mitigation.

Required waiver metadata (MUST):

- `waiver_id`,
- gate being waived,
- rationale,
- owner,
- expiry date,
- rollback/mitigation plan,
- reference to approval note.

Expired waivers MUST automatically become NO-GO until renewed or resolved.

### GO / conditional GO / NO-GO decision matrix

- **GO**
  - all release gates pass,
  - no unresolved determinism failure on required benchmark windows.
- **conditional GO**
  - non-critical gate miss with explicit mitigation + short-term follow-up owner,
  - no determinism failure in closed-window replay.
- **NO-GO**
  - determinism gate fails on closed window,
  - explainability coverage < 100%,
  - precision/drift regressions exceed allowed thresholds without approved waiver.

### Conditional GO usage policy (draft)

- Allowed on `task/*` branches for controlled iteration when:
  - determinism gate passes,
  - explainability coverage is complete,
  - remaining gate misses have active mitigation plans.
- Not allowed for final `main` merge readiness unless maintainer explicitly
accepts the conditional risk in writing.
- Not allowed for release promotion tags (`release/*` to publish path).

## Product contract split

UI/CLI must separate:

1. observed hours,
2. classified hours,
3. approved invoice hours.

Do not present classified output as invoice truth unless explicitly approved.

## Implementation roadmap

### Phase A (MVP hardening)

- Add evidence payload fields to report/session output.
- Add `decision_class` and confidence buckets.
- Add benchmark runner over fixed fixture months.
- Add "hour drift" report against truth set.
- Add deterministic replay checker and payload hash report.
- Add explicit volatile-field allowlist used by replay checker.

### Phase B (Operator workflow)

- Review queue for `maybe` sessions.
- One-click accept/reject with persisted decisions.
- Rule suggestions ranked by expected precision gain.

### Phase C (Standard candidate v1)

- Publish versioned "Timelog Truth Format" spec.
- Publish baseline benchmark pack and reproducible script.
- Freeze compatibility window for downstream tools.

### Phase D (Operational enforcement)

- Add CI job for deterministic replay on closed benchmark windows.
- Publish policy package changelog with migration notes.
- Add release template requiring GO/conditional GO/NO-GO declaration.

## Implementation handoff checklist (ready-for-build)

Use this checklist when implementing Timelog Truth Standard components.

Compliance note:

- Items in this checklist are **MUST** unless explicitly marked as implementation
sequencing guidance.

1. **Contract wiring**
  - add per-session fields: `decision_class`, `confidence_score`,
   `matched_evidence`, `negative_evidence`, `input_fingerprint`,
   `determinism_status`, `determinism_reasons`,
  - add run-level reproducibility block fields.
2. **Policy packaging**
  - emit full policy package contract in output metadata,
  - ensure policy-affecting changes bump contract version fields.
3. **Deterministic replay tooling**
  - implement payload normalizer + volatile-field stripper,
  - implement deterministic hash computation and diff report.
4. **Benchmark runner**
  - execute month-level + annual/all-project protocol,
  - emit required artifacts (`benchmark_manifest.json`,
  `benchmark_metrics.json`, `determinism_replay_report.json`).
5. **Gate evaluation**
  - evaluate numeric gates and produce GO/conditional GO/NO-GO result,
  - enforce waiver policy constraints (no determinism waiver on closed windows).
6. **Operator visibility**
  - expose decision split (observed/classified/approved) in CLI/UI output,
  - ensure explainability payload is inspectable for every session.

## Implementation slices (execution order)

### Slice 1: Reproducibility metadata foundation

Goal:

- emit run-level reproducibility block and policy package metadata in report
payload.

Primary targets:

- `core/truth_payload.py`
- `core/engine_api.py`
- `tests/` payload-contract coverage

Definition of done:

- required reproducibility keys are present in JSON payload output,
- schema contract tests pass.

Definition of ready:

- required run-level key list is finalized,
- payload versioning path is agreed.

### Slice 2: Session evidence + determinism fields

Goal:

- attach per-session evidence and determinism fields to session outputs.

Primary targets:

- `core/domain.py`
- `core/report_aggregate.py`
- `core/report_service.py`

Definition of done:

- every session includes required evidence keys,
- explainability coverage reaches 100% on benchmark fixtures.

Definition of ready:

- evidence key names and types are locked for current schema version,
- benchmark fixtures include representative session diversity.

### Slice 3: Deterministic replay checker

Goal:

- implement deterministic hash + replay comparison tooling.

Primary targets:

- `scripts/` (replay checker utility),
- `core/calibration/` (shared replay helpers),
- CI wiring in `.github/workflows/ci.yml` (non-blocking first, then enforcing).

Definition of done:

- replay checker emits `determinism_replay_report.json` (per canonical artifact
format),
- closed-window replay pass/fail is machine-evaluable.

Definition of ready:

- volatile-field allowlist is documented and versioned,
- closed-window benchmark range is available.

### Slice 4: Annual + all-project benchmark runner

Goal:

- run month-level + annual aggregate validation for all active projects.

Primary targets:

- `scripts/ci/run_cli_experiments_ci.py` (or adjacent benchmark runner),
- `core/calibration/experiments.py`,
- benchmark fixtures/manifests under `out/` artifacts in CI.

Definition of done:

- emits `benchmark_manifest.json` and `benchmark_metrics.json` (per canonical
artifact format),
- annual coverage gate and project inclusion status are reported.

Definition of ready:

- active-project threshold policy is available for current cycle,
- benchmark year/month/project scope is frozen.

### Slice 5: Gate decision and operator surfacing

Goal:

- produce GO/conditional GO/NO-GO decision output and expose split views in UX.

Primary targets:

- `core/cli_report_status.py`
- `outputs/terminal.py`
- release/runbook docs for gate interpretation

Definition of done:

- gate decision visible and reproducible from artifacts,
- observed/classified/approved split is clearly visible to operators.

Definition of ready:

- GO/conditional GO/NO-GO policy text is approved,
- operator-facing copy for split views is aligned with product language.

## Artifact format (minimum required keys)

### `benchmark_manifest.json`

- `target_year`
- `months_in_scope`
- `projects_in_scope`
- `project_inclusion_reasons`
- `project_exclusions`
- `policy_package`

### `benchmark_metrics.json`

- `precision_recall_f1_by_project`
- `customer_hour_drift`
- `review_load`
- `explainability_coverage`
- `annual_coverage`
- `gate_decision` (`GO` | `conditional GO` | `NO-GO`)
- `gate_failures`

### `determinism_replay_report.json`

- `replay_runs`
- `payload_hashes`
- `normalized_equal`
- `volatile_field_allowlist_version`
- `drift_keys` (empty on pass)
- `determinism_status`

### `README.md` (artifact guide)

- window used for this run,
- replay result summary (`normalized_equal`, `gate_decision`),
- file-by-file interpretation guide for reviewers.

## Validation report template (required per slice)

Use this exact compact shape in implementation notes and PR validation:

- `Expected:` what should be true after the slice
- `Observed:` what actually happened
- `Evidence:` paths to cast/test/artifact outputs

Minimum evidence requirements:

- at least one deterministic replay check for slices affecting determinism,
- targeted unit/integration tests for modified contracts,
- one concise artifact sample path for review.

Current evidence anchor for replay checker script contract:

- `tests/test_timelog_truth_check_script.py` validates open-window guard behavior
and required artifact generation for `scripts/timelog_truth_check.sh`.
- Operational usage and reviewer flow: `docs/runbooks/timelog-truth-check.md`.

## Risks

- Overfitting rules to one user's behavior.
- High review burden if thresholds are too strict.
- Source quality variance across machines/environments.

Mitigation: benchmark diversity, calibration profiles, and explicit uncertainty.

## Open decisions

- Default thresholds for `work`/`maybe`/`personal_or_unclear`.
- Minimum evidence needed for auto-billable recommendation.
- How to version and distribute truth sets safely.
- Allowed non-deterministic metadata fields (for example `generated_at`) and how
they are excluded from replay diff checks.
- Final numeric values for active-project threshold after first benchmark cycle.
- Whether "business-critical" project flag should be manual only or policy-derived.

## Success criteria

This RFC is successful when a monthly report can answer:

- Why each hour belongs to a project/customer,
- How certain the system is,
- How much deviates from approved invoice truth,
- Which policy/version produced the result.