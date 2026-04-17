# CI and repository gates

## Branch protection model (`dev` + `main`)

The repository uses two protected branches with different review intent:

- **`dev`**: day-to-day integration quality gate (`task/* -> dev`).
- **`main`**: release/integration gate (`dev -> main`), release-ready history only.

Both branches block direct pushes and require pull requests.

## Integration branch (`dev`)

The repository now uses **`dev`** as the default integration branch for contributor/agent work:

- new work starts on `task/*` branches from `dev`,
- PRs merge into `dev`,
- stable `dev` is promoted via PR into `main`.

`release/X.Y.Z` remains available for explicit version-isolation work.

## GitHub settings checklist

Configure this in **GitHub -> Settings -> Branches** (or Rulesets) for both branches.

### `dev` protection (integration gate)

- Require a pull request before merging.
- Require status checks to pass before merging:
  - `python`
  - `package`
  - `extension`
- Require conversation resolution before merging.
- Dismiss stale pull request approvals when new commits are pushed.
- Require linear history (optional but recommended).
- Disable force pushes and branch deletion.

### `main` protection (release/integration review gate)

- Require a pull request before merging.
- Restrict expected merge path to `dev -> main` for routine releases.
- Require status checks to pass before merging:
  - `python`
  - `package`
  - `extension`
- Require conversation resolution before merging.
- Require at least one maintainer approval for `dev -> main`.
- Dismiss stale pull request approvals when new commits are pushed.
- Disable force pushes and branch deletion.

This keeps feature-level review load on `dev`, while preserving a final release
gate on `main`.

## Workflow location

- **File:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- **Triggers:** `push` and `pull_request` (so PRs and the merge target both run checks).

- **PyPI publish:** [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml) — builds sdist + wheel and publishes on **version tags** `v*.*.*` or **workflow_dispatch** (requires [trusted publishing](https://docs.pypi.org/trusted-publishers/) on PyPI). See **`docs/versioning.md`**.

- **GitHub Pages (landing site):** [`.github/workflows/static.yml`](../.github/workflows/static.yml)

## GitHub Pages (`gittan.sh` / project site)

| Trigger | What happens |
|---------|----------------|
| **Push to `main`** | Runs [`scripts/prepare_static_site.sh`](../scripts/prepare_static_site.sh) to build `_site`, then **deploys** to the configured Pages URL. **`deploy`** has `pages: write` + `id-token: write`; workflow default is `contents: read` only. |
| **Pull request → `main`** | Runs **`verify-static-site`** only (same script, **no** Pages/OIDC permissions), **no** publish. |
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
- **Branch flow:** default contributor path is `task/* -> dev`; PRs to `main` should normally be release/integration PRs.

## Related

- **`BRANCH.md`** — feature-branch workflow when `main` is protected.
- **`CONTRIBUTING.md`** — contributor setup and tests.
