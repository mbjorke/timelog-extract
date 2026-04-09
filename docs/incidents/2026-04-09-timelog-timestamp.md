# Incident: Invented `TIMELOG.md` clock time

**Date:** 2026-04-09  
**Severity:** Low (data quality / trust in local timelog)  
**Status:** Mitigated

## Summary

An agent appended a `TIMELOG.md` entry using a **placeholder clock time** (`18:00`) that did not match the user’s actual local time (~07:53 on the same calendar day).

## Impact

- The log line looked valid but was **misleading** for retrospectives and trust in the timelog.
- The failure mode is easy to repeat unless policy and checks are explicit.

## Root cause

- No written rule required **deriving** `HH:MM` from the real environment or from an explicit user-provided time.
- The agent **inferred** a time instead of running `date` or asking.

## Fix

- **`AGENTS.md`** now requires real local wall time, forbids invented/placeholder times, and documents obtaining time via `date '+%Y-%m-%d %H:%M'` or user-stated time, else ask.
- **Regression test:** `tests/test_agents_timelog_policy.py` fails CI if those policy strings are removed or weakened from `AGENTS.md`.

## What automated tests cannot do

CI cannot prove an AI will always follow the policy. The test only **guards the documented rule** in-repo so it is not accidentally deleted during refactors.

## Verification

- `python3 -m pytest tests/test_agents_timelog_policy.py -q`
- Read `AGENTS.md` → Standard Timelog Policy.
