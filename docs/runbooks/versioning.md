# Package versioning

The **Python package** version (what `pip` installs and what `gittan -V` / `timelog-extract -V` prints) is the single number in `pyproject.toml` under `[project] version`.

We follow a practical **SemVer-style** rule of thumb:

| Bump | When |
|------|------|
| **MAJOR** | Breaking CLI or public Python API changes you expect consumers to react to. |
| **MINOR** | New features, new optional flags, or larger behavior changes that stay backward compatible for typical scripts. |
| **PATCH** | Bug fixes and small safe corrections. |

A large merge to `main` with many CLI and licensing changes may warrant **0.2.0** even if the previous line was **0.1.0** — use judgment and describe the release in `CHANGELOG.md`.

## Release workflow: maintainer vs agent

| | **Maintainer (you)** | **Agent / automation** |
|---|----------------------|-------------------------|
| **Goal** | Ship a version users can install or read about | Prepare the branch, files, tests, and conflict fixes |
| **GitHub** | Open PR → merge when CI is green; optional Draft / CodeRabbit | Push branch, summarize PR status in plain language |
| **Version files** | Approve scope (which X.Y.Z) | Edit `pyproject.toml`, `core/cli_options.py`, `CHANGELOG.md` per checklist below |
| **PyPI** | Configure trusted publisher; trigger tag or workflow | Remind checklist; local `python -m build` when packaging changes |
| **Terminology** | “Merge the PR”, “tag the release” is enough | Avoid assuming the maintainer knows `rebase`, `squash`, or `fetch` unless they ask |

When someone says **“I want a new release”**, interpret it as: **do the technical release prep** and **spell out the remaining GitHub/PyPI clicks** — see **`AGENTS.md`** (“Releases: what the maintainer means vs what the agent does”).

### After squash merge: follow-up commits on `release/X.Y.Z`

This repo often **squash-merges** PRs into `main`. That rewrites history: **`main` will not contain the same commits** as the release branch, only a **single new commit**. If you **continue the same branch name** (`release/0.2.3`) with more commits and open **another** PR, GitHub may report **conflicts** in `CHANGELOG.md`, `README.md`, or similar.

**Agent fix (typical):** from the release branch:

```bash
git fetch origin
git merge origin/main
# resolve conflicts, then:
git commit   # completes the merge
git push origin release/X.Y.Z
```

Prefer **combining** unrelated follow-up work into **one** PR per version when possible to reduce this friction; if follow-up is unavoidable, merging `main` back into the release branch before merge is normal.

## Checklist when bumping the package version

There is **no single automated `release` command** in this repository — follow the steps below (and run **`./scripts/run_autotests.sh`** before pushing the version bump). Optional: **`bash scripts/compare_gittan_versions.sh`** (pipx `gittan` vs repo) on a few date windows before tagging — see script header for `--from` / `--to`. Tagging and PyPI are separate steps after **`main`** contains the bump commit.

1. Set **`pyproject.toml`** → `[project] version` to `X.Y.Z`.
2. Update the **dev fallback** in **`core/cli_options.py`** (`package_version()`) to `X.Y.Z-dev` so runs without an editable install still report a sensible string.
3. **GitHub HTTP `User-Agent`** is built from `package_version()` in `collectors/github.py` — no separate version string to edit.
4. Add a **`CHANGELOG.md`** section `## X.Y.Z - YYYY-MM-DD` and move items out of **Unreleased** as appropriate.
5. After the bump is on **`main`**: `git tag -a vX.Y.Z -m "Release X.Y.Z"` and `git push origin vX.Y.Z`.

### Git tag ≠ GitHub Release

A **git tag** (`v0.3.1`) is enough for the PyPI workflow and for `git describe`. The GitHub **Releases** page (and the green **Latest** badge) only moves when a **Release object** exists for that tag.

Pushing `v*.*.*` runs [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml), which:

1. Publishes the wheel/sdist to PyPI (trusted publishing).
2. After publish succeeds, creates a GitHub Release from the matching
   `CHANGELOG.md` section (`scripts/changelog_section.py`) and marks it **Latest**.
   Headings must be dated (`## X.Y.Z - YYYY-MM-DD`); draft sections are rejected.
If you only tagged historically and never opened a Release, the UI can still show an older **Latest** (e.g. tags `v0.3.0` / `v0.3.1` existed while Releases stopped at `v0.2.17`).

**Backfill a missing Release** for an existing tag (from repo root, after `git fetch --tags`):

```bash
set -euo pipefail
VERSION=0.3.1   # no leading v
TAG=v${VERSION}
python3 scripts/changelog_section.py "$VERSION" > /tmp/notes.md
{
  echo "**Install:** \`pip install -U timelog-extract\` / \`curl -fsSL https://gittan.sh/install | bash\`"
  echo
  cat /tmp/notes.md
} > /tmp/body.md
gh release create "$TAG" --title "$TAG" --notes-file /tmp/body.md --verify-tag --latest
```

Use `--latest=false` when backfilling an older tag that must not steal **Latest** from a newer Release.

## PyPI distribution

**Scope and backlog:** [`docs/legacy/release-scope-0.2.3.md`](../legacy/release-scope-0.2.3.md).

The project is a normal **setuptools** package (`pyproject.toml`, `[project] name = "timelog-extract"`). **0.2.3** adds automated **build + publish** via [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml) using [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). Until the first upload succeeds, your PyPI profile will say **“You have not uploaded any projects”** — that is normal.

**Maintainer steps for the first upload**

1. **Register a pending trusted publisher** (before any project appears on PyPI):
   - Log in → **[Account settings → Publishing](https://pypi.org/manage/account/publishing/)** (or **Manage account** on your profile, then **Publishing**).
   - Add **GitHub** as the publisher and fill in roughly:
     - **Owner:** `mbjorke`
     - **Repository name:** `timelog-extract`
     - **Workflow name:** `pypi.yml` — the **filename** under `.github/workflows/` (must end in `.yml` or `.yaml`), **not** the workflow’s human-readable `name:` in the YAML (e.g. not “Publish to PyPI”).
     - **Environment name:** leave **empty** (this repo’s workflow does not use a GitHub Environment).
   - Save. PyPI will allow the **Publish to PyPI** GitHub Action to create **`timelog-extract`** on first successful run. Official reference: [Adding a pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-pending-publisher/).
2. On GitHub, ensure **`main`** has the release you want (e.g. version **0.2.3** in `pyproject.toml`), then:
   - `git tag -a v0.2.3 -m "Release 0.2.3"` and `git push origin v0.2.3`.
   - That tag push runs **`pypi.yml`**: PyPI publish **and** a GitHub Release (so the Releases page **Latest** badge updates). Manual **Actions → Publish to PyPI → Run workflow** still publishes to PyPI but does **not** create a GitHub Release (tag-only job).
3. After the workflow turns green, open **`https://pypi.org/project/timelog-extract/`** and **`https://github.com/mbjorke/timelog-extract/releases`** — smoke-test: `python3 -m pip install timelog-extract` and `gittan -V`.

Local dry-run (no upload):

```bash
python -m pip install build
python -m build
```

**Manual upload** (token-based) remains possible with `twine` if you do not use the GitHub workflow.

## Install script (`https://gittan.sh/install`)

The one-line installer [`packaging/install/gittan-install.sh`](../../packaging/install/gittan-install.sh) is **version-agnostic**: it runs `pipx install timelog-extract` (or `pip install --user`), which resolves the latest release from PyPI at install time. Consequences for releases:

- **Normal release:** no change to the script. Bump → tag → PyPI as above; `curl -fsSL https://gittan.sh/install | bash` picks up the new version automatically.
- **Only when installer behavior changes:** edit `packaging/install/gittan-install.sh` in this repo, then mirror the file to the separate [`gittan-home`](https://github.com/mbjorke/gittan-home) repo as `install`. `gittan.sh` is served from `gittan-home` (Cloudflare Pages deploys on push to its `main`), so the mirrored file goes live only after that repo's `main` deploys. Until that mirror lands, `curl … | bash` still serves the previous installer.
- Pin a release for users/CI: `curl -fsSL https://gittan.sh/install | bash -s -- --version X.Y.Z`.
- Clear a PATH shadow (Anaconda / old pip winning over pipx): re-run `curl -fsSL https://gittan.sh/install | bash` (shadow cleanup is the default; `--no-fix-shadow` keeps other installs).

The Homebrew tap (see [`homebrew-tap.md`](homebrew-tap.md)) remains an optional, separate distribution track with its own per-release formula maintenance.

## Not the same: JSON truth payload `version`

`--format json` output includes a **`version`** field inside the payload that describes the **truth-payload schema** (an integer contract for automation), not the PyPI package version. See `docs/legacy/v1-tag-annotation-draft.md` and `docs/runbooks/cli-first-v1-release-checklist.md`.
