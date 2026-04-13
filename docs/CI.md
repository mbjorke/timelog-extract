# CI and repository gates

## `main` is branch-protected

The default branch **`main`** does **not** accept direct pushes from contributors. Changes merge via **pull request** only (typically **squash merge**). This is enforced by **GitHub branch protection**, not by the workflow file alone.

Treat **`main` as read-only** from local clones unless a maintainer performs an allowed merge. See **`BRANCH.md`** for the git workflow.

## Workflow location

- **File:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- **Triggers:** `push` and `pull_request` (so PRs and the merge target both run checks).

- **PyPI publish:** [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml) — builds sdist + wheel and publishes on **version tags** `v*.*.*` or **workflow_dispatch** (requires [trusted publishing](https://docs.pypi.org/trusted-publishers/) on PyPI). See **`docs/VERSIONING.md`**.

- **GitHub Pages (landing site):** [`.github/workflows/static.yml`](../.github/workflows/static.yml)

## GitHub Pages (`gittan.sh` / project site)

| Trigger | What happens |
|---------|----------------|
| **Push to `main`** | Builds `_site` from `gittan.html` + static assets and **deploys** to the configured Pages URL (production). |
| **Pull request → `main`** | Runs **`verify-static-site`** only: same copy steps, **no** publish. This checks that the bundle is valid before merge. |
| **`workflow_dispatch`** | **Re-deploy** production from the current `main` tip (Actions → *Deploy static content to Pages* → *Run workflow*). Use if a deploy failed or Pages was misconfigured. |

### Why the PR says “This branch has not been deployed”

GitHub’s **Deployments** UI tracks environments such as **`github-pages`** when a workflow **publishes** to that environment. We **only attach that environment on pushes to `main`**, not on PR branches — so feature/release branches correctly show as **not deployed** until you **merge**. After merge, the **push** to `main` runs **`deploy`**; if the site does not update, open **Actions** and check the latest **Deploy static content to Pages** run (or trigger **workflow_dispatch**).

PRs still get a **green workflow** from **verify-static-site** when site-related files change; that is separate from the deployment badge.

## Jobs

| Job | What it does |
|-----|----------------|
| **python** | Editable install, smoke `timelog_extract.py --today` (non-fatal), **500-line** cap per Python file (`scripts/check_file_lengths.py`), **`scripts/run_autotests.sh`**. |
| **package** | `python -m build` (sdist + wheel), then `pip install` the wheel and run `timelog-extract -V` / `gittan -V`. |
| **extension** | In `cursor-extension/`: `npm install`, `npm run build`. |

## PR expectations (not auto-enforced in YAML)

- **PR title and description in English** — see **`AGENTS.md`** and [`.github/pull_request_template.md`](../.github/pull_request_template.md). The workflow does not detect language; it is a project rule for reviewers and bots.

## Related

- **`BRANCH.md`** — feature-branch workflow when `main` is protected.
- **`CONTRIBUTING.md`** — contributor setup and tests.
