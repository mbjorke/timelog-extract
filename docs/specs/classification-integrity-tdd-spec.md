# Spec: Classification Integrity (TDD-first)

Status: draft
Date: 2026-04-23

## Problem

Users can lose trust when:

- broad or overlapping `match_terms` assign hours to the wrong project,
- report/status tables look additive while aggregation models differ.

## Scope

Implement minimum safe changes with tests first:

1. Config overlap/risk linting
2. Clear total-vs-project attribution semantics in status output
3. Deterministic classifier tie handling with tests

## Test-first tasks

### 1) Overlap lint

Add tests for a helper that flags enabled-profile term collisions:

- same term in multiple enabled profiles -> warning
- same term where one profile is disabled -> no warning
- repo-path overlap -> warning

### 2) Status integrity

Add tests that enforce one of:

- additive mode: totals equal project sum, or
- overlap mode: explicit label that project rows are overlapping attribution

No silent mixed semantics.

### 3) Classifier ties

Add unit tests in `tests/test_core_domain.py` (or equivalent):

- equal score among projects should follow explicit rule (e.g. priority field or deterministic policy),
- tracked URL hits outrank weak generic term hits.

## Implementation notes

- Keep backward compatibility where possible.
- Prefer warnings first, then stricter gating once false positives are low.
- Do not introduce cloud dependency or external services.

## Exit criteria

All new tests pass, and a recreated problematic day no longer misattributes
customer hours under the same input traces/config.
