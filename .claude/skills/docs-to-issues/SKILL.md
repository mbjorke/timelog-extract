---
name: docs-to-issues
description: Turn the repo's planning docs (docs/task-prompts specs + their Gherkin) into GitHub issues, idempotently — a one-time backlog import and ongoing sync. Use when converting written plans/specs/gherkin into trackable tickets, populating the project board, or "make issues from the docs".
---

# docs-to-issues

Thin wrapper. Read and follow the canonical workflow:
**`docs/skills/docs-to-issues.md`**.

Engine: `scripts/docs_to_issues.py` — one issue per `docs/task-prompts/*.md` spec
(title + Traceability + Gherkin acceptance criteria), **idempotent** via a hidden
`<!-- docs2issue: <path> -->` marker so re-runs never duplicate. Done specs skipped.

- **Dry-run first:** `python scripts/docs_to_issues.py` → review the list.
- Apply: `python scripts/docs_to_issues.py --apply` (add `--project 3` to also put
  them on the board — needs the `project` gh scope).
- Then hand off to **`gittan-product-owner`** to prioritize the issues.

Policy: **`AGENTS.md`**.
