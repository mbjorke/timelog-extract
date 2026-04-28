# Specs implementation status

Status: active tracker  
Last updated: 2026-04-28

## Purpose

Keep one fast, shared view of which specs are built, partially built, or still planned.

## Status scale

- `not started`: no meaningful implementation landed yet.
- `partial`: some scoped pieces are implemented; exit criteria not fully met.
- `built`: core implementation landed for the stated scope.
- `verified`: built and validated with explicit evidence (tests/runbook/usage checks).

## Current matrix


| Spec                                                   | Current status | Notes / evidence anchor                                                                                                          |
| ------------------------------------------------------ | -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `docs/specs/report-search-refactor-plan.md`            | `verified`     | Shared helpers are live in `core/cli_report_status.py` and tests pass in full autotest gate.                                     |
| `docs/specs/triage-onboarding-timestamp-spike-spec.md` | `partial`      | S1 (timestamp hints) is built; S2/S3 follow-up still pending per spec text.                                                      |
| `docs/specs/live-terminal-sandbox-demo.md`             | `partial`      | P1 allowlist + deterministic demo server/worker behavior is implemented; later hardening phases remain.                          |
| `docs/specs/ab-rule-suggestions.md`                    | `partial`      | `suggest-rules` / `apply-suggestions` and integrated `review --ab-suggestions` exist; spec remains draft-v2 experiment contract. |
| `docs/specs/classification-integrity-tdd-spec.md`      | `not started`  | Still draft; parts may exist in code, but full TDD scope and exit criteria are not yet closed.                                   |
| `docs/specs/timelog-truth-standard-rfc.md`             | `partial`      | RFC is active; replay tooling baseline exists, but full slice-level DoD remains open (see Timelog Truth DoD Snapshot below).     |


## Update routine

When a spec changes implementation state:

1. Update the row in this file.
2. Add one concrete evidence anchor (test file, command validation, or PR/commit ref).
3. If status reaches `verified`, ensure the validation evidence is durable and reproducible.

## Timelog Truth DoD Snapshot

Status date: 2026-04-28

| Slice | Current state | Done now | Remaining for DoD |
| --- | --- | --- | --- |
| Slice 1: Reproducibility metadata foundation | `partial` | Truth payload contract and schema plumbing exist; payload versioning and engine API boundaries are in place. | Add explicit run-level reproducibility block keys in standard format and lock tests for required keys. |
| Slice 2: Session evidence + determinism fields | `not started` | No full session-level evidence contract in output yet. | Emit `decision_class`, confidence, matched/negative evidence, fingerprint, and determinism fields for every session. |
| Slice 3: Deterministic replay checker | `partial` | Replay/check tooling and script contract exist (`scripts/timelog_truth_check.sh`, `tests/test_timelog_truth_check_script.py`). | Align output fully to RFC artifact contract and enforce closed-window pass/fail semantics in CI-ready form. |
| Slice 4: Annual + all-project benchmark runner | `not started` | No complete annual/all-project benchmark artifact pipeline yet. | Produce `benchmark_manifest.json` + `benchmark_metrics.json` with active-project coverage accounting and reproducible commands. |
| Slice 5: Gate decision + operator surfacing | `not started` | GO/conditional GO/NO-GO contract documented only. | Surface gate decision and observed/classified/approved split in operator UX (`status`/report surfaces). |

Notes:

- This keeps `docs/specs/timelog-truth-standard-rfc.md` as normative source; this section is execution tracking only.
- Update this table whenever a slice crosses `not started` -> `partial` -> `built` -> `verified`.