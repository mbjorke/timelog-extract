# Task prompt: Orchestrate `dev` ↔ `main` alignment (agent → agent / human)

*Paste into a **GitHub Issue**, **Cursor Cloud**, or a second agent session. Replace placeholders. Keep the issue **English** for public tool compatibility if the repo is public. After execution: brief note on the issue (English); add a line to [`docs/ideas/til/`](../ideas/til/) **only** if something was **actually learned** that day — otherwise document assumptions or outcomes under [`docs/ideas/`](../ideas/) or close [issue #66](https://github.com/mbjorke/timelog-extract/issues/66) (see [`til/README.md`](../ideas/til/README.md)).*

## Traceability

- story_id: `GH-66` (tracked with dev alignment; see repo issue)
- spec_status: `approved`
- implementation_status: `not built` (operational runbook — execution is out-of-band)
- created_at: `2026-04-18`
- last_updated_at: `2026-04-19`
- implementation.pr: pending (N/A until alignment executed)
- implementation.branch: pending
- implementation.commits: []
- validation.evidence: pending (post `git rev-parse origin/main origin/dev` match after C1)
- validation.decision: `NO-GO` until maintainer runs tag + C1 per runbook
- changelog:
  - `2026-04-18: Handoff prompt created.`
  - `2026-04-19: Traceability block added; placeholder origin/dev fix.`
  - `2026-04-19: Pre-conditions checklist added (aligns with CodeRabbit “next steps” agent plan).`
  - `2026-04-19: Success criteria + paste-instructions aligned with TIL vs ideas distinction.`
  - `2026-04-19: Documented canonical test command: bash scripts/run_autotests.sh from repo root (CONTRIBUTING parity).`

## Objective

Safely realign branch **`dev`** with **`main`** when histories have **diverged** (e.g. tens of unique commits on each side). **Canonical product state is on `main`** (PyPI, releases). **No force-push to `main`**.

## Pre-conditions (checklist before execution)

- [ ] Phase A output exists (merge-base, SHAs, left-right counts) — paste into the issue or this handoff.
- [ ] Maintainer accepts **C1** (reset `dev` to `main`) or explicitly chooses C2/C3 — see runbook.
- [ ] GitHub **branch protection** on `dev` allows **tag push** and planned **force-with-lease** (or exception is scheduled).
- [ ] No open PRs **into** `dev` that must land before reset (or they are abandoned / retargeted).
- [ ] Executor will run **`bash scripts/run_autotests.sh`** from **repository root** after local reset and before force-push (same as [`CONTRIBUTING.md`](../../CONTRIBUTING.md); do not rely on `./` if the script is not executable).

## Inputs (fill before sending)

- **Repository:** `owner/timelog-extract` (or as applicable).
- **Phase A snapshot** (from an agent with clone access) — **paste verbatim:**

```text
merge-base:
origin/main: <sha>
origin/dev:  <sha>
left-right  origin/main...origin/dev:  <A> <B>   (explain which side is "only on main" / "only on dev" in one line)
diff tail (last lines of --stat or note "large; see issue"):
```

- **Owner decision (human):** Path **C1** (reset `dev` to `main` + force-with-lease) vs **C2/C3** only if required — from [`../runbooks/dev-main-alignment.md`](../runbooks/dev-main-alignment.md).

- **Blockers known:** (e.g. *branch protection forbids force on `dev` until YYYY-MM-DD*.)

## Instructions for the executing agent

1. Read **`docs/runbooks/dev-main-alignment.md`** end to end. Do not skip the **tag backup** of current `dev`.
2. Use **`gh`** in the environment when the maintainer’s token allows; otherwise return **ready-to-paste** commands and **one** `gh` issue comment template for the maintainer.
3. After any local reset rehearsal on a throwaway clone, run **`bash scripts/run_autotests.sh`** from **repository root** on the **tree** you intend to push (the `main` tree for C1).
4. **Handoff to next agent in cloud / thread:** a single **comment** containing: tag name of archive, final `dev` sha after success (should match `main` for C1), and **C1** vs **C2** vs **C3** used.

## Success criteria

- Old `dev` is **addressable** via a tag.
- `origin/dev` matches **`origin/main`** for **C1** (same `git rev-parse` after fetch).
- Outcome **documented** for others: at minimum a closing comment on the tracking issue **in English**; optional **TIL** in `docs/ideas/til/` only for genuine learnings (not assumptions — see [`til/README.md`](../ideas/til/README.md)).
- **Done** when the orchestrating agent (or human) has **committed and pushed** (or equivalent `gh` merge) as described in the runbook; use explicit words, not internal abbreviations (see [`../inspiration/effective-commands-for-agents.md`](../inspiration/effective-commands-for-agents.md)).

## Non-goals

- Rebasing or force-pushing **`main`**.
- Silent bypass of org branch protection; escalate to maintainer with exact **Settings** path and **date**.
