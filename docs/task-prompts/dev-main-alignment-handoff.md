# Task prompt: Orchestrate `dev` ↔ `main` alignment (agent → agent / human)

*Paste into a **GitHub Issue**, **Cursor Cloud**, or a second agent session. Replace placeholders. Keep the issue **English** for public tool compatibility if the repo is public; internal notes can stay in Swedish in `docs/ideas/til/` after.*

## Objective

Safely realign branch **`dev`** with **`main`** when histories have **diverged** (e.g. tens of unique commits on each side). **Canonical product state is on `main`** (PyPI, releases). **No force-push to `main`**.

## Inputs (fill before sending)

- **Repository:** `owner/timelog-extract` (or as applicable).
- **Phase A snapshot** (from an agent with clone access) — **paste verbatim:**

```text
merge-base:
origin/main: <sha>
origin/dev:  <sha>
left-right  origin/main...origin_dev:  <A> <B>   (explain which side is "only on main" / "only on dev" in one line)
diff tail (last lines of --stat or note "large; see issue"):
```

- **Owner decision (human):** Path **C1** (reset `dev` to `main` + force-with-lease) vs **C2/C3** only if required — from [`../runbooks/dev-main-alignment.md`](../runbooks/dev-main-alignment.md).

- **Blockers known:** (e.g. *branch protection forbids force on `dev` until YYYY-MM-DD*.)

## Instructions for the executing agent

1. Read **`docs/runbooks/dev-main-alignment.md`** end to end. Do not skip the **tag backup** of current `dev`.
2. Use **`gh`** in the environment when the maintainer’s token allows; otherwise return **ready-to-paste** commands and **one** `gh` issue comment template for the maintainer.
3. After any local reset rehearsal on a throwaway clone, run **`./scripts/run_autotests.sh`** on the **tree** you intend to push (the `main` tree for C1).
4. **Handoff to next agent in cloud / thread:** a single **comment** containing: tag name of archive, final `dev` sha after success (should match `main` for C1), and **C1** vs **C2** vs **C3** used.

## Success criteria

- Old `dev` is **addressable** via a tag.
- `origin/dev` matches **`origin/main`** for **C1** (same `git rev-parse` after fetch).
- Documented in repo TIL or issue **in English** (brief) for external contributors.
- **Done** when the orchestrating agent (or human) has **committed and pushed** (or equivalent `gh` merge) as described in the runbook; use explicit words, not internal abbreviations (see [`../inspiration/effective-commands-for-agents.md`](../inspiration/effective-commands-for-agents.md)).

## Non-goals

- Rebasing or force-pushing **`main`**.
- Silent bypass of org branch protection; escalate to maintainer with exact **Settings** path and **date**.
