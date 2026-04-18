# Task (deferred): CodeRabbit Autofix — CI guardrails

*Exploratory follow-up. **Not** policy until merged into [`AGENTS.md`](../../AGENTS.md) or a runbook.*

**Maintainer stance (assumption / decision — not a TIL):** comfortable **trusting Autofix** for now; the main **operational** risk is **CI going red** if a change slips through. No change to `AGENTS.md` or workflows **that evening** — “locked” until a follow-up PR. *This belongs in `ideas/` because it is a working position, not “something learned today” — see [`til/README.md`](til/README.md).*

**Context (2026-04-19):** Same as above; formalize guardrails when picked up.

## When you pick this up

- [ ] Add a **short** subsection under [`AGENTS.md`](../../AGENTS.md) → *Review Cadence (CodeRabbit)*: after applying Autofix (or merging an Autofix branch), **confirm CI is green** before merging to `main`; if red, **revert or fix forward** with the same discipline as any other PR.
- [ ] Optional: one line in [`.github/pull_request_template.md`](../../.github/pull_request_template.md) checklist — *“If Autofix or bot commits: verified CI on latest push.”*
- [ ] Optional: link [CodeRabbit docs](https://docs.coderabbit.ai/) on Autofix / Finishing Touch — product behavior changes; keep our file to **principles**, not vendor UI steps.

## Non-goals

- Changing branch protection or adding new workflows **only** for Autofix unless a concrete gap appears.
- Blocking Autofix — this task is **guardrails**, not a ban.

## Done when

 Maintainer is comfortable that the **default** path after Autofix is **see green CI**, then merge — documented in one canonical place.
