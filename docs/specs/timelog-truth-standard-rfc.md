# RFC: Timelog Truth Standard

Status: Draft
Owner: Maintainer + AI agents

## Why this RFC

Current reporting is useful but heuristic-heavy. For a world-standard ambition, we
need a model that is reproducible, auditable, and measurable against explicit
"truth" references, not just plausible classification.

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

## Terminology

- **Observed time**: activity inferred from data sources (browser, IDE, mail, git).
- **Classified time**: observed time mapped to project/customer by rules/model.
- **Invoice time**: human-approved billable time for invoicing.
- **Truth set**: labeled reference data used to evaluate the classifier.

## Principles

1. **Determinism first**: same inputs + same rule/model version => same result.
2. **Evidence over guessing**: each classified session includes reason codes.
3. **Human authority**: invoice decisions remain explicit until confidence is proven.
4. **Version everything**: config, model behavior, output schema, evaluation set.

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

This enables reproducible audits and explanations.

## Evaluation framework

### Truth sets

- Build labeled monthly samples (multiple customers/projects patterns).
- Keep train/validation slices separate from exploratory tuning.

### Core metrics

- project-level precision/recall/F1,
- customer-hour error (absolute + signed drift),
- false-positive rate on personal browsing,
- review load (% sessions in `maybe`),
- stability metric (delta after rule updates on unchanged input).

### Release gates (draft)

- no regression on precision beyond agreed threshold,
- customer-hour drift below gate for benchmark months,
- explainability coverage: 100% sessions have evidence payload.

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

### Phase B (Operator workflow)

- Review queue for `maybe` sessions.
- One-click accept/reject with persisted decisions.
- Rule suggestions ranked by expected precision gain.

### Phase C (Standard candidate v1)

- Publish versioned "Timelog Truth Format" spec.
- Publish baseline benchmark pack and reproducible script.
- Freeze compatibility window for downstream tools.

## Risks

- Overfitting rules to one user's behavior.
- High review burden if thresholds are too strict.
- Source quality variance across machines/environments.

Mitigation: benchmark diversity, calibration profiles, and explicit uncertainty.

## Open decisions

- Default thresholds for `work`/`maybe`/`personal_or_unclear`.
- Minimum evidence needed for auto-billable recommendation.
- How to version and distribute truth sets safely.

## Success criteria

This RFC is successful when a monthly report can answer:

- Why each hour belongs to a project/customer,
- How certain the system is,
- How much deviates from approved invoice truth,
- Which policy/version produced the result.

