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

It also **prioritizes the issue backlog**: specs become issues via
`/docs-to-issues` (idempotent), then this skill sets each issue's priority
(`priority:now|next|later|do-not-build` label) and reflects it on the project
board (needs the `project` gh scope for board fields). Flow: fuzzy ask → spec →
issue → prioritized on the board.

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
