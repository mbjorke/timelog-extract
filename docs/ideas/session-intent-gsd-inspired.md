# Session Intent: GSD-Inspired Focus Layer

Status: future idea
Source: GitHub issue #104 / CodeRabbit planning note

## Why Save This

CodeRabbit proposed a concrete GSD-inspired feature set around session intent:
record planned work, start/end focused sessions, compare intent with observed
activity, and surface verification in reports.

The idea is valuable, but it is not the current beta blocker. The near-term
blocker is time-to-useful-project-config: users need a fast, trustworthy path
from local evidence to useful project mappings before a new session workflow
adds enough value.

## Useful Product Idea

Add a local session intent layer that lets a user declare planned work before a
focused pass and compare it with collected activity afterward.

Potential commands:

- `gittan session start --plan "..." --project "..."`
- `gittan session status`
- `gittan session end --summary "..."`
- `gittan session list`
- `gittan session show <id>`

Potential storage:

- `.gittan/sessions.json`
- separate from `TIMELOG.md`
- local-first, not committed by default

Potential session fields:

- `id`
- `started_at`
- `planned_work`
- `target_project`
- `ended_at`
- `actual_summary`
- `status` (`active`, `completed`, `abandoned`)

## Truth Standard Alignment

This should be framed as planned evidence, not invoice truth:

- planned work is user-declared intent,
- collected events are observed evidence,
- intent-vs-actual comparison is a review aid,
- approved invoice time remains a separate human decision.

This maps well to `docs/specs/timelog-truth-standard-rfc.md`, especially the
split between observed time, classified time, and approved invoice time.

## Why Not Now

Do not implement this before beta onboarding friction is reduced.

Reasons:

- It adds new CLI surface before project config setup is easy.
- It does not solve the first-run problem for users without useful mappings.
- Pipeline/report integration would increase blast radius.
- The current demo story is stronger when focused on evidence-first config
  onboarding and the Timelog Truth Standard.

## Better Order

1. Guided project config onboarding: evidence -> suggestions -> approval.
2. Truth Standard foundations: evidence payloads, decision classes, confidence.
3. Session intent as planned evidence.
4. Invoice approval workflow.

## Possible First Increment Later

Start with a narrow, non-reporting MVP:

1. Store local sessions in `.gittan/sessions.json`.
2. Support `session start`, `session status`, and `session end`.
3. Do not change report totals.
4. At `session end`, show a small observed activity summary for the time window.

Only integrate into the main report payload after the storage model and UX prove
useful in real sessions.
