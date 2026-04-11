# Gittan Vision (English Reference)

## Why Blueberry built Gittan

Automatic time reporting has been a long-standing dream for many developers.

Now it is practical.

Blueberry built Gittan to solve the real gap between how people actually work and how time reporting usually gets reconstructed afterward.

## The real-world problem

A typical day is fragmented:
- coding,
- terminal work,
- browser context switching,
- AI-assisted tasks,
- frequent commits,
- interruptions and quick pivots.

Even disciplined builders who commit often still end up reconstructing their day manually when it's time to report.

## What Gittan does differently

Gittan builds reporting from real computer activity signals.

Users choose which sources should represent a specific day, for example:
- browser-tab-level activity,
- git history,
- or a combined source view.

Users can compare source quality with one click and switch source mix per day.

## Core product intent

Gittan is designed to be:
- local-first,
- practical,
- trust-oriented,
- low-friction in daily work.

It is not meant to force a single tracking model on everyone.
It is meant to let users select the evidence quality that fits each day and workflow.

## Local-first vs cloud agents

**Local-first** means the default reporting story does not depend on uploading raw activity to *our* servers. It does **not** mean pretending cloud work does not exist.

When developers delegate work to **cloud agents**, important evidence often lives with the provider (runs, spend, artifacts). Gittan’s direction is to support **optional, consent-based connectors** that pull **job-level metadata** from those platforms so reporting can reflect **human + agent** outcomes—not only local file churn.

Privacy expectations stay the same: **explicit scope**, **minimal data**, and **no Gittan-operated data lake** as the default path.

## User promise

Less manual reconstruction.
More accurate reporting confidence.
Clearer client-facing and review-ready outputs.

## Scope note

This document is a narrative companion to:
- `docs/GITTAN_VISION.md`
- `docs/GITTAN_NORTHSTAR_METRICS.md`
- `docs/V1_SCOPE.md`
- `VISION.md` (repository root) — short public one-pager; not authoritative on scope

See `docs/VISION_DOCUMENTS.md` for the full hierarchy.

If there is wording conflict, product behavior and guardrails in `GITTAN_VISION.md`, `GITTAN_NORTHSTAR_METRICS.md`, and `V1_SCOPE.md` take precedence over this file and over root `VISION.md`.
