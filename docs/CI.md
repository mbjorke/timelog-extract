# CI and repository gates

## `main` is branch-protected

The default branch **`main`** does **not** accept direct pushes from contributors. Changes merge via **pull request** only (typically **squash merge**). This is enforced by **GitHub branch protection**, not by the workflow file alone.

Treat **`main` as read-only** from local clones unless a maintainer performs an allowed merge. See **`BRANCH.md`** for the git workflow.

## Workflow location

- **File:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- **Triggers:** `push` and `pull_request` (so PRs and the merge target both run checks).

## Jobs

| Job | What it does |
|-----|----------------|
| **python** | Editable install, smoke `timelog_extract.py --today` (non-fatal), **500-line** cap per Python file (`scripts/check_file_lengths.py`), **`scripts/run_autotests.sh`**. |
| **extension** | In `cursor-extension/`: `npm install`, `npm run build`. |

## PR expectations (not auto-enforced in YAML)

- **PR title and description in English** — see **`AGENTS.md`** and [`.github/pull_request_template.md`](../.github/pull_request_template.md). The workflow does not detect language; it is a project rule for reviewers and bots.

## Related

- **`BRANCH.md`** — feature-branch workflow when `main` is protected.
- **`CONTRIBUTING.md`** — contributor setup and tests.
