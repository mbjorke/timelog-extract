# Spec: triage onboarding timestamp spike (S1-first)

Status: S1 built; S2/S3 pending
Date: 2026-04-21
Related idea: `docs/ideas/triage-onboarding-spike-2026-04.md`

## Goal

Improve onboarding speed and mapping confidence by enriching triage output with
minimal timestamp context for top sites, while preserving current privacy and
read-only guarantees.

## Scope

This spec defines a small first increment:

- S1: timestamp hints in `gittan triage --json` (built)
- S2/S3 planning hooks (not full implementation in this step)

## Implementation status

S1 is implemented in `core/cli_triage.py` and covered by
`tests/test_cli_triage.py`.

Validation evidence:

- `python3 -m unittest tests/test_cli_triage.py`

## Non-goals

- No GUI redesign.
- No remote backend dependencies.
- No change to `--json` read-only behavior.
- No page-title exposure.

## Current baseline

`gittan triage --json` returns per-day:

- `top_sites`: domain, visits, share
- suggestions / automation fields

Before S1, it did not provide temporal anchors to help users decide "which
project this site belonged to around that time."

## Proposed S1 contract change (schema v1 additive)

Add optional time hints to each `top_sites` item:

```json
{
  "domain": "github.com",
  "visits": 12,
  "share": 0.33,
  "first_seen_local": "2026-04-21T09:12:00+03:00",
  "last_seen_local": "2026-04-21T10:47:00+03:00",
  "sample_window_local": {
    "start": "2026-04-21T09:40:00+03:00",
    "end": "2026-04-21T09:55:00+03:00"
  }
}
```

Notes:

- Fields are optional; missing values are allowed.
- Keep `schema_version` at `1` for this additive change.
- Use local timezone timestamps (`isoformat`) for onboarding readability.
- No page titles or raw URL paths.

## Data derivation rules

For each day + domain in top sites:

1. `first_seen_local`: earliest event timestamp for that domain on that day.
2. `last_seen_local`: latest event timestamp for that domain on that day.
3. `sample_window_local`:
   - if a matching session window exists, use that window;
   - else use a short fallback around a representative event timestamp;
   - if unavailable, omit the field.

## CLI behavior constraints

- `gittan triage --json` remains read-only.
- Output remains single JSON object on stdout.
- Existing keys stay stable; added fields must not break old consumers.

## Truth Standard alignment

This increment supports `docs/specs/timelog-truth-standard-rfc.md` by adding
reviewable evidence to onboarding without treating the suggestion as invoice
truth:

- `top_sites` domains and local timestamp hints are observed evidence.
- `suggestions`, `question`, and `choices` are classified candidates.
- `gittan triage-apply` remains the explicit human-approved write path.
- Page titles and raw URL paths stay out of JSON to reduce accidental PII.

## Tests (required)

1. Unit tests for serializer output:
   - includes new keys when timestamps available
   - omits keys cleanly when unavailable
2. Regression test:
   - existing required keys still present
   - no title/path leakage in JSON

Suggested location:

- `tests/test_cli_triage.py` (extend existing JSON plan tests)

## Validation plan (S2/S3 follow-up)

After S1 lands:

1. Run one baseline onboarding pass (current flow).
2. Run one timestamp-enriched pass.
3. Record in idea doc:
   - time to first apply
   - accepted mappings count
   - uncategorized delta

If no measurable win, stop and document rejection rationale.

## Rollout

1. S1 implemented in `core/cli_triage.py` plan assembly.
2. Runbook contract updated: `docs/runbooks/gittan-triage-agents.md`.
3. Next: run S2/S3 comparison and record whether timestamp hints reduce
   time-to-first-useful-config.

## Phase-2 hook (customer bootstrap + top-sites)

After setup-first customer bootstrap v1 is validated, use those seeded
project/customer anchors to prioritize top-sites suggestions in triage:

- setup v1: explicit top project/customer seeds (question-first)
- triage v2: rank site/domain suggestions against seeded anchors before proposing writes
- keep read-only by default in `gittan triage --json` until user approval
