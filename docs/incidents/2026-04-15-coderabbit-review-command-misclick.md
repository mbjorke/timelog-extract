# Incident: CodeRabbit review command misclick

Date: 2026-04-15  
Status: Closed (process guardrails added)

## Summary

A review command was triggered at the wrong time in a PR flow (command-level
"misclick"), causing unnecessary review churn and avoidable rate-limit pressure.

## Impact

- Extra review cycle without meaningful new code delta.
- Increased risk of hitting CodeRabbit hourly review caps.
- Slower PR progression due to noise instead of focused feedback.

## Root cause

- Operational ambiguity between:
  - `@coderabbitai full review` (full pass), and
  - `@coderabbitai review` (incremental pass).
- Review command fired before branch state was stable.

## Corrective actions

1. Clarified review cadence and command intent in `AGENTS.md`.
2. Added explicit guidance to batch pushes before requesting full review.
3. Added rate-limit fallback note to prefer CLI/local pre-check when needed.

## Preventive checklist (before any CodeRabbit trigger)

- [ ] Branch scope is stable for this review cycle.
- [ ] CI is green (or expected green for latest push).
- [ ] No immediate follow-up commit is planned.
- [ ] Command chosen intentionally:
  - full pass: `@coderabbitai full review`
  - incremental pass: `@coderabbitai review`

## Validation

- Team can now map review intent to command explicitly.
- Expected outcome: fewer accidental review runs and lower rate-limit churn.
