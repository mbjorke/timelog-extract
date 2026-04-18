# Private local business notes (not committed)

Some material is **too sensitive or premature** for the public repository (pitch decks, unpublished pricing, raw LinkedIn drafts, investor-only narrative). The codebase and docs should still stay **reviewable** and **honest**.

**Default rule:** anything about **money, metrics, or personal/business performance** that you would not put on a public slide belongs in **`private/`**, not in committed markdown. That includes **revenue, runway, targets, conversion, cohorts, sponsor-specific numbers**, and **internal dashboards** — even if anonymized, aggregates can still be sensitive.

## Recommended pattern

1. Add a **`private/`** directory **next to or inside** your clone (see `.gitignore` — the name `private/` is ignored).
2. Store files there; **never** `git add` them. If something is accidentally staged, unstage before commit.
3. Open the same folder in Cursor if you want agents to **read** context during a session—there is no persistent cross-session “memory” unless you save it in **committed** docs or **Cursor rules** you control.

## GitHub funding metadata

Public **Sponsor** links for this repo are defined in **`.github/FUNDING.yml`** (tracked). You can still use **Repository Settings → Sponsorships** if you prefer UI-only configuration, but there is no need to keep a separate funding YAML under **`private/`** unless you are experimenting with drafts you do not want to commit yet.

## What stays in the repo instead

- **`docs/ideas/opportunities.md`** — shareable, English, **strategic** opportunities and risks (audience, bets, differentiation). Not the place for channel-by-channel marketing execution.
- **`LICENSE`** and **`docs/business/sponsorship-terms.md`** — binding terms for distribution and team-scale use.

## Public `ideas/opportunities.md` vs local `private/` (how to split)

| Topic | Prefer **public** (`ideas/opportunities.md` or other committed docs) | Prefer **`private/`** (never commit) |
|-------|------------------------------------------------------------------|----------------------------------------|
| Who the product serves; CLI-first bet; backlog priorities | Yes — aligns reviewers and contributors | — |
| Risks that affect **trust** (scope creep, overclaim) | Yes | — |
| **LICENSE / sponsorship** consistency with public copy | Summaries in repo; legal text stays in `LICENSE` | Personal “what we’d *like* to charge” before legal review |
| **LinkedIn / social** post drafts, hooks, posting calendar | Only high-level notes if needed for context | **Full drafts**, dates, A/B variants |
| **Test rabbit** / beta recruitment wording | One honest line in `OPPORTUNITIES` is enough | Concrete DMs, names, commitments |
| Revenue targets, runway, investor-only narrative | — | **Always private** until you choose to publish |
| **Metrics** (KPIs, MAE calibration raw sheets, sponsor hours, internal scorecards) | High-level **product** metrics that define the tool (e.g. north-star *definitions* in `docs/product/gittan-northstar-metrics.md`) — without live numbers | **Actual values**, trends, experiments, or anything tied to real customers |
| Competitor notes, pricing experiments, Patreon tier experiments | Illustrative drafts may live in `docs/business/patreon-positioning.md` (already marked draft) | **Numbers and promises** you are not ready to stand behind |

**Later**, when you "move business to private," you can **shorten** `ideas/opportunities.md` to thesis + risks + pointers, and keep **richer** business notes only under `private/`.

## What automated reviewers (e.g. CodeRabbit) should emphasize

Ask for a **business / product** pass on **strategy, scope honesty, and doc consistency**-not **marketing execution** (headlines, campaigns). Tie comments to **files changed in the PR** and to **`docs/ideas/opportunities.md`** when it is touched.

## Agents

Follow **`AGENTS.md`**: do not commit `TIMELOG.md` or local `private/` content.
