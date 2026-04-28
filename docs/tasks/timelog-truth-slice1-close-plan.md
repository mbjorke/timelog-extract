# Timelog Truth Slice 1 Close Plan

Status: planning only (no implementation started)
Last updated: 2026-04-28

## Goal

Close Slice 1 (Reproducibility metadata foundation) by locking run-level payload contract fields and test coverage before implementation.

## Task list

- [ ] `slice1-prep-scope-freeze` Freeze Slice 1 key list and payload placement before implementation.
- [ ] `slice1-prep-integration-map` Map each Slice 1 field to source (`truth_payload`, `engine_api`, runtime/options) and mark placeholder values.
- [ ] `slice1-prep-test-strategy` Define pre-implementation contract test strategy (presence, types, enum/defaults, key-removal regression).
- [ ] `slice1-lock-key-list` Lock final run-level reproducibility key names and placement according to RFC contract.
- [ ] `slice1-implement-payload-block` Implement reproducibility block and policy metadata emission in truth payload path.
- [ ] `slice1-contract-tests` Add/expand contract tests for required reproducibility keys and deterministic defaults.
- [ ] `slice1-validate-gates` Run targeted tests and full autotest gate for Slice 1 changes.
- [ ] `slice1-update-status` Update implementation status snapshot with Slice 1 evidence and state transition.

## RFC-required keys (Slice 1)

- `input_snapshot_id`
- `policy_version`
- `schema_version`
- `timezone_basis`
- `determinism_status`
- `determinism_reasons`

## Primary target files (when implementation starts)

- `core/truth_payload.py`
- `core/engine_api.py`
- `tests/test_truth_payload.py`
- `docs/specs/implementation-status.md`
