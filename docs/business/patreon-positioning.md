# Patreon positioning (draft source material)

**Status:** Working notes for Patreon and other fundraising copy — **not** a commitment to ship specific perks or prices. This file is non-binding positioning material and should stay aligned with `LICENSE`, `docs/product/v1-scope.md`, `docs/security/privacy-security.md`, and `docs/product/vision-documents.md`.

This file captures positioning discussed during early product/marketing brainstorming (including third-party suggestions) so the repo stays the single place to refine the narrative.

---

## Why Patreon fits Gittan

Much of the “AI tool” market is moving toward **expensive subscriptions** and **cloud-only** data. Gittan is positioned as the opposite: **local**, **privacy-first**, and **professional** — a credible story for supporters who want independent tooling.

## Value proposition: “found money”

For freelancers and consultants, Gittan is not only a log: it helps surface **under-reported or forgotten billable time**. If the tool helps recover even a small amount of missed billable time, supporter pricing can be easy to justify — but **do not promise specific dollar ROI** on the Patreon page without evidence; keep it qualitative or add pilot data later.

## Positioning line

- **“The AI developer’s sidekick”** — many products sell “AI coders”; Gittan focuses on **evidence and reconstruction**: what the human + AI stack actually did, locally.

## Suggested tier sketch (revise before publish)

These are **illustrative** tiers from brainstorming — rename, reprice, or drop perks to match what you can deliver and support.

| Tier | Sketch | Notes |
|------|--------|--------|
| **Supporter** (~$5/mo) | Supporters who want the project to stay **local and open**. Optional cosmetic perk discussed: a small **“Gittan” marker in the CLI** (e.g. next to the header) — **only if** you want to build and maintain it; avoid implying paywalled core features. |
| **Power user** (~$15/mo) | **Early access** to the optional **Cursor extension** (companion to the CLI, not required for core value) + channel for **priority requests** for new sources (Firefox, Jira, etc.) — scope requests realistically. |
| **Agency / hands-on** (~$50/mo) | **Direct help** setting up complex `timelog_projects.json` and **custom PDF branding** — clearly separate from the open-source core; spell out limits (hours, SLA) when you offer this. |

**CLI-first reminder:** Core reporting remains the **CLI / script path**; extension and PDF branding are **add-ons**, not prerequisites. See `README.md` and `docs/product/vision-documents.md`.

## Marketing angles / taglines (pick and test)

- “Gittan knows what you did last Tuesday.”
- “The privacy-first auditor for the AI-assisted developer.”
- “Stop losing billable hours to the ‘AI flow state’.”

Root `VISION.md` uses a shorter variant of the last theme (“Stop guessing. Start billing. Gittan knows.”) — keep taglines consistent across Patreon, README, and video descriptions.

## Sustainability target (maintainer)

Financial goals are not legal terms, but they guide **what tier design must support**. A **2×** return on a year’s invested effort is too low to be interesting; **10×** on a **one-year** horizon is a **healthy “more than satisfied” bar** for sustainable development—achievable through a mix of Patreon tiers, team-scale sponsorship, and optional hands-on services (see tier sketch above), not through low-tier volume alone.

## Before you publish on Patreon

- [ ] Tiers match what you can deliver (badge, extension access, support hours).
- [ ] Wording does not contradict **local-first** or **consent** (`docs/security/privacy-security.md`).
- [ ] No promise of cloud processing or data leaving the machine unless you explicitly add that product.
- [ ] Update **`VISION.md`** if the public one-liner changes.
