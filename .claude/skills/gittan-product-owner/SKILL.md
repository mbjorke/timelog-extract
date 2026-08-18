---
name: gittan-product-owner
description: Plan fuzzy Gittan product work AND prioritize the issue backlog — turn concerns into an ordered, behavior-ready backlog (priorities, acceptance criteria, Gherkin) and prioritize the GitHub issues / project board, without writing code. Use when prioritizing, shaping a backlog, ordering the board, slicing a feature, deciding "build X before Y?", or writing requirements.
---

# gittan-product-owner

Thin wrapper. Read and follow the canonical workflow:
**`docs/skills/gittan-product-owner.md`**.

This is a planning pass — produce an ordered backlog (`now`/`next`/`later`/`do
not build yet`) with acceptance criteria and Gherkin where useful; do **not**
write code. Start product framing from `docs/product/vision-documents.md`.

It also **prioritizes the backlog**, but it does **not open issues**. Priority
lives in the committed spec, and in `priority:*` labels on issues that already
exist. An issue is a work record: it is opened when someone starts the work, by
whoever starts it. Flow: fuzzy ask → spec → prioritized → issue at work start.

Measured 2026-08-18: opening issues at prioritization time made 25% of the open
backlog planning artifacts with a 41-day median age, while 49 of 80 closed
issues closed the same day they were opened. See the *Issue lifecycle* section
of the canonical doc.

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
