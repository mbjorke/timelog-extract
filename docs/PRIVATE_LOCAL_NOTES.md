# Private local business notes (not committed)

Some material is **too sensitive or premature** for the public repository (pitch decks, unpublished pricing, raw LinkedIn drafts, investor-only narrative). The codebase and docs should still stay **reviewable** and **honest**.

## Recommended pattern

1. Add a **`private/`** directory **next to or inside** your clone (see `.gitignore` — the name `private/` is ignored).
2. Store files there; **never** `git add` them. If something is accidentally staged, unstage before commit.
3. Open the same folder in Cursor if you want agents to **read** context during a session—there is no persistent cross-session “memory” unless you save it in **committed** docs or **Cursor rules** you control.

## What stays in the repo instead

- **`docs/OPPORTUNITIES.md`** — shareable, English, product-level opportunities and risks.
- **`LICENSE`** and **`docs/SPONSORSHIP_TERMS.md`** — binding terms for distribution and team-scale use.

## Agents

Follow **`AGENTS.md`**: do not commit `TIMELOG.md` or local `private/` content.
