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

1. Set **`pyproject.toml`** → `[project] version` to `X.Y.Z`.
2. Update the **dev fallback** in **`core/cli_options.py`** (`package_version()`) to `X.Y.Z-dev` so runs without an editable install still report a sensible string.
3. **GitHub HTTP `User-Agent`** is built from `package_version()` in `collectors/github.py` — no separate version string to edit.
4. Add a **`CHANGELOG.md`** section `## X.Y.Z - YYYY-MM-DD` and move items out of **Unreleased** as appropriate.
5. Tagging on Git (optional): `git tag -a vX.Y.Z -m "Release X.Y.Z"` after the version commit is on the branch you intend to release.

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
2. On GitHub, ensure **`main`** has the release you want (e.g. version **0.2.3** in `pyproject.toml`), then either:
   - `git tag -a v0.2.3 -m "Release 0.2.3"` and `git push origin v0.2.3`, **or**
   - **Actions → Publish to PyPI → Run workflow** (uses the same `pypi.yml`).
3. After the workflow turns green, open **`https://pypi.org/project/timelog-extract/`** — the project should exist. **Smoke-test:** `python3 -m pip install timelog-extract` and `gittan -V`.

Local dry-run (no upload):

```bash
python -m pip install build
python -m build
```

**Manual upload** (token-based) remains possible with `twine` if you do not use the GitHub workflow.

## Not the same: JSON truth payload `version`

`--format json` output includes a **`version`** field inside the payload that describes the **truth-payload schema** (an integer contract for automation), not the PyPI package version. See `docs/v1-tag-annotation-draft.md` and `docs/runbooks/cli-first-v1-release-checklist.md`.
