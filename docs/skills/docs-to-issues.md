# docs-to-issues — turn planning docs into GitHub issues

Canonical workflow for the `/docs-to-issues` skill. Converts the repo's planning
docs into GitHub issues **idempotently**, so the written backlog (task-prompts +
Gherkin) becomes trackable tickets — a one-time import *and* ongoing sync.

Engine: `scripts/docs_to_issues.py`. Pairs with `gittan-product-owner` (which then
**prioritizes** the issues on the project board).

## What becomes an issue

- **Primary unit: `docs/task-prompts/*.md`** — one issue per spec. The `# Title` is
  the issue title; the `## Traceability` (`story_id`, `spec_status`,
  `implementation_status`) and the ```gherkin``` Behavior Contract become the body
  (acceptance criteria). Gherkin scenarios ride *inside* the spec's issue — not 45
  separate feature-issues.
- Specs whose `implementation_status` is done/shipped are **skipped** (unless
  `--include-done`).

## Idempotency

Every generated issue carries a hidden marker `<!-- docs2issue: <path> -->`. A re-run
lists existing markers (`gh issue list --search docs2issue`) and skips any spec that
already has an issue. So it is safe to run repeatedly as new specs land.

## Run it

```bash
python scripts/docs_to_issues.py                 # dry-run: list what would be created
python scripts/docs_to_issues.py --apply         # create the issues
python scripts/docs_to_issues.py --apply --project 3   # + add to project board (needs project scope)
python scripts/docs_to_issues.py --include-done  # also include already-built specs
```

- **Always dry-run first** and eyeball the list.
- `--project N` needs the `project` gh scope (`gh auth refresh -s project`); without
  it, issues are created (repo scope) and can be added to the board later.

## Workflow

1. Dry-run → review the candidate list (title, story_id, gherkin count per spec).
2. `--apply` to create the missing issues.
3. Hand off to **`gittan-product-owner`** to prioritize them (`now/next/later/do
   not build`) and set board fields.

Policy (branches, safety, PR language): **`AGENTS.md`**.
