# Gittan Vision and Soul

**Companion docs:** Root `VISION.md` is a short external manifesto (e.g. Patreon) and must stay aligned with this file. See **`VISION_DOCUMENTS.md`** for precedence when multiple vision docs exist.

## Why this exists

Gittan exists to solve one practical problem:

People do real work across many tools, but reporting still depends on memory.

The result is stress, missed billable time, weak customer-facing explanations, and unnecessary admin.

Gittan turns scattered work traces into a clear, local-first, review-ready picture of what actually happened.

## One-line north star

**From scattered traces to trusted work truth.**

## Product soul (what must always be true)

1. **Local first, user in control**  
   Core reporting works without uploading raw traces to *our* infrastructure. Optional connectors may read **from third-party services you choose** (for example cloud agent APIs) using **your** credentials, under explicit consent—still aligned with privacy-by-default in `PRIVACY_SECURITY.md`.

2. **Proof over performance theater**  
   Output should be understandable, reviewable, and tied to concrete traces.

3. **Reduce cognitive load**  
   Gittan should remove manual reconstruction work, not add new admin rituals.

4. **Trust is a feature**  
   Privacy defaults, explicit consent, and predictable behavior are part of the product.

5. **Practical over perfect**  
   Better weekly confidence now beats theoretical completeness later.

## Who Gittan is for

- Freelancers and consultants who bill from real delivery work
- Small teams with high context-switching across tools
- Dev/Ops-heavy workflows where activity is distributed and hard to summarize manually

## What Gittan is (and is not)

### Gittan is

- A local-first reporting engine
- A workflow that produces both human-readable and machine-readable output
- A bridge between modern AI-assisted work and defensible reporting

### Gittan is not

- A surveillance product
- A cloud-first telemetry platform
- A payroll/compliance timesheet system
- "Track everything" software with unlimited source sprawl

## Local-first and cloud-native work (including agents)

**Local-first** does not mean “ignore the cloud.” It means: **default processing and sensitive traces stay on the user’s side**, and **no cloud backend is required** for Gittan’s core story.

A growing share of developer work is **delegated to cloud agents**. If Gittan only ingested purely local files, it would **under-report** the same work that customers pay for—because runs, tokens, artifacts, and sometimes outcomes live **with the provider**.

The product direction is therefore:

- **Keep** the reporting engine and primary evidence **local-first** and **reviewable**.
- **Add** optional, **consent-based** “remote signals” that summarize **what agents did**—typically **metadata** (job IDs, timestamps, cost, links to outputs, PRs) rather than full prompt dumps—so the user can defend **human + agent** value in one narrative.

This must remain compatible with trust: **explicit scope**, **minimal collection**, and **no surprise exfiltration** to Gittan-operated servers. Where cloud visibility is needed, it should be **user-directed API access** to **their** vendor relationships, not a generic telemetry pipeline.

## Core promises

- **Clear weekly reconstruction** from real traces
- **Client-facing and review-ready reporting** with low friction
- **Structured outputs** for automation and integrations
- **Configurable source scope** with explicit user control

## Current maturity statement

Gittan is fast-moving.  
The extension UX is evolving.  
The core local reporting engine is already used in pilot workflows.

## Mapping to Blueberry north star and metrics

This document is intentionally aligned with:

- `blueberry/private/northstar.md`
- `blueberry/private/metrics.md`

### Mission mapping

Blueberry mission: bridge rapid AI prototyping with production-ready, GDPR-compliant systems.

Gittan mapping:
- turns fast, fragmented AI-assisted work into production-usable reporting truth,
- keeps privacy/trust constraints first (consent, local-first baseline),
- helps teams move quickly without losing accountability.

### Vision mapping

Blueberry vision: be the Nordic go-to partner for speed without broken trust.

Gittan mapping:
- provides a concrete "trust layer" for delivery evidence,
- strengthens customer-facing reporting quality,
- supports Blueberry's positioning as practical, compliance-aware AI implementation.

### R2-D2 mentality mapping

Northstar says: focused, loyal, willing to protest bad judgment.

Gittan mapping:
- focused scope (avoid "track everything" creep),
- loyal to user-owned local data and explicit consent,
- protests bad product judgment via the decision filter (do not ship features that reduce trust clarity).

### Experiment culture mapping

Northstar says: do not guess, experiment/measure/iterate.

Gittan mapping:
- accuracy loop in `ACCURACY_PLAN.md`,
- KPI-driven improvement rather than intuition-only feature work,
- weekly review rhythm tied to measurable deltas.

### Metrics mapping (from `private/metrics.md`)

Gittan should influence these Blueberry metric families:

- **Pipeline metrics**  
  Better reporting clarity should improve conversion trust in late-stage conversations.

- **Website metrics**  
  Clear Gittan narrative should lift inquiry rate and close rate on productized offers.

- **Content/social metrics**  
  Case-study + pilot posts should increase inbound DMs and qualified conversations.

- **Health metrics**  
  Gittan directly supports billable vs non-billable clarity by reducing reporting reconstruction time.

### Practical scoreboard for Gittan (derived)

Use these as working product-health indicators:

1. Accuracy KPI trend from `docs/ACCURACY_PLAN.md`
2. Time-to-report/export in real pilot usage
3. Pilot-to-active usage conversion
4. User-reported confidence in customer-facing reporting
5. Reduction in manual weekly reconstruction time

## Roadmap intent (how existing docs connect)

This vision is implemented through the existing docs in `docs/`:

- **Product boundary and UX scope:** `V1_SCOPE.md`
- **Privacy baseline and consent rules:** `PRIVACY_SECURITY.md`
- **Accuracy targets and measurement loop:** `ACCURACY_PLAN.md`
- **Architecture simplification and service boundary:** `docs/archive/agentic-evaluation.md`
- **Risk posture from adjacent products:** `RISK_PATTERNS_FROM_UPSTREAM.md`
- **Audience narratives:** `docs/archive/case-study.md` and `docs/archive/case-study-tech.md`

If future decisions conflict with this document, the default is:
1. keep local-first trust guarantees,
2. keep reporting clarity,
3. avoid scope creep.

## Decision filter (use before adding features)

Before shipping a new source, output, or workflow step, ask:

1. Does this improve trusted reporting quality?
2. Does this reduce or increase user admin burden?
3. Can this stay local-first by default, with any cloud/agent access **optional**, **explicit**, and **minimal**?
4. Does it preserve explicit consent and privacy expectations?
5. Is this in-scope for v1/v1.1, or just technically possible?

If the answer is mostly "no", do not ship it yet.

## Voice and personality

Gittan should feel:

- calm,
- practical,
- honest,
- quietly competent.

Not hype-heavy, not vague, not over-claiming.

## Short external framing

Blueberry built Gittan because modern work is fragmented but accountability is not.  
When teams move fast across tools, they still need a trustworthy way to explain what was done.

Gittan gives that explanation from real traces, with local-first control.
