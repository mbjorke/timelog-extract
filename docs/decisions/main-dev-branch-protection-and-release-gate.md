# Decision: Protect `dev` and keep release gate on `main`

Status: Accepted (historical); **workflow superseded (April 2026)** — see [`BRANCH.md`](../../BRANCH.md)  
Date: 2026-04-15  
Owner: Maintainer + active agent

## Status update (April 2026)

Upstream **no longer uses a standing `dev` branch** on GitHub: default integration path is **`task/* -> main`**. The **protected `main` + PR-only** rule remains. The body below records the earlier two-branch intent; for current settings, use **`docs/runbooks/ci.md`** and **`BRANCH.md`**.

## Context

The project moved to `task/* -> dev -> main` flow, but branch protection and
review expectations needed to be explicit for both protected branches.

## Decision

1. Protect **both** `dev` and `main` in GitHub (no direct pushes).
2. Keep `dev` as integration branch for day-to-day feature work:
   - `task/* -> dev` remains the default contributor and agent path.
3. Keep `main` as release/integration branch:
   - normal promotion is `dev -> main`.
   - `dev -> main` requires release/integration review before merge.
4. Keep CodeRabbit auto-review enabled, but throttle manual review triggers to
   one per stable batch (documented in `AGENTS.md`).

## Consequences

- Better integration safety: unstable work is filtered before `main`.
- Clear release ownership: `main` becomes a deliberate promotion gate, not just
  another merge target.
- Lower review noise: most iteration stays in `task/* -> dev`, and `main` review
  focuses on release readiness.

## Implementation notes

- Branch protection details and checklist are documented in `docs/runbooks/ci.md`.
- Branch intent and workflow are documented in `BRANCH.md`.
- Agent behavior and review cadence are documented in `AGENTS.md`.
