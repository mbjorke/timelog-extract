# Values — timelog-extract / Gittan

*Culture and product posture for this repo. Machine-facing rules stay in [`AGENTS.md`](../../AGENTS.md). Visual and metaphor: [`IDENTITY.md`](IDENTITY.md).*

*Inspired in part by the culture sections of [Blueberry Maybe](https://blueberry.ax) (parent company; internal source: `values` in the Blueberry repo) — adapted here for an open-source, local-trust product.*

---

## Craft over noise

We respect the **craft** of reliable tooling: small surfaces, clear defaults, tests before push. We do not ship “vibes only” when correctness and user data are on the line.

---

## Honest, small surface

- **Honest** — We say when something is rough, missing, or wrong, including in docs and changelogs.
- **Focused** — Gittan does not try to be every productivity app; it connects **local activity → review-ready** output.
- **Reliable** — Breaking config or timelog behavior without migration notes is a failure mode we avoid.

---

## Patience and fundamentals

We fix root causes when we can, not only symptoms. We document decisions that affect contributors ([`docs/decisions/`](../decisions/)) so the next person is not guessing. “Wax on, wax off” still applies: boring fundamentals keep the product trustworthy.

---

## Instinct + verification

We trust good product sense — and we **verify** with tests, evals, and real CLI runs. We experiment, measure, and iterate; we do not mistake a clever prompt for a proof.

---

## Nordic-flavored trust (product + community)

- **Trust** is earned through consistency in releases and communication, not hype.
- **Transparency** in what the tool does and does not read on disk (see [`docs/security/`](../security/)).
- **Long-term** care for users who build habits around their logs.
- **Simplicity** in CLI and docs as a sign of respect for people’s time.

---

## What we won’t do

- Mislead about data handling or “what gets sent where.”
- Take shortcuts that create **compliance or recovery debt** for users’ local work history.
- Pretend a broken edge case is fine “for now” on critical paths without tracking it.
- **Oversell** in marketing copy relative to what the current release actually does (see [IDENTITY](IDENTITY.md) and changelogs).

---

## Autonomy and ownership

The best work on this project comes from people (and **agents** following the same bar) who **own** their change: small PRs, clear intent, and respect for [`AGENTS.md`](../../AGENTS.md) gatekeeping. Creative freedom is **in scope**, not a license to ignore tests or private-data rules.

---

*If you need one word internally: the “soul” of the project is the combination of **this file** and **IDENTITY** — we keep `values.md` as the explicit name so newcomers find it; “soul” is optional shorthand in chat, not a second file.*
