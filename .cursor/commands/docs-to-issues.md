---
description: Turn planning docs (task-prompts + Gherkin) into GitHub issues, idempotently
---

# `/docs-to-issues`

Thin wrapper. Canonical workflow: **`docs/skills/docs-to-issues.md`**.

**Use when:** converting written plans/specs/Gherkin into trackable tickets, or
populating the project board.

**Mechanics:**
- Engine `scripts/docs_to_issues.py` — one issue per `docs/task-prompts/*.md` (title +
  Traceability + Gherkin as acceptance criteria). Idempotent via a hidden
  `<!-- docs2issue: <path> -->` marker; done specs skipped.
- **Dry-run first:** `python scripts/docs_to_issues.py`; then `--apply` (and
  `--project 3` for the board — needs `gh auth refresh -s project`).
- Hand off to `/gittan-product-owner` to prioritize.

Policy: **`AGENTS.md`**.
