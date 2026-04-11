# Package versioning

The **Python package** version (what `pip` installs and what `gittan -V` / `timelog-extract -V` prints) is the single number in `pyproject.toml` under `[project] version`.

We follow a practical **SemVer-style** rule of thumb:

| Bump | When |
|------|------|
| **MAJOR** | Breaking CLI or public Python API changes you expect consumers to react to. |
| **MINOR** | New features, new optional flags, or larger behavior changes that stay backward compatible for typical scripts. |
| **PATCH** | Bug fixes and small safe corrections. |

A large merge to `main` with many CLI and licensing changes may warrant **0.2.0** even if the previous line was **0.1.0** — use judgment and describe the release in `CHANGELOG.md`.

## Checklist when bumping the package version

1. Set **`pyproject.toml`** → `[project] version` to `X.Y.Z`.
2. Update the **dev fallback** in **`core/cli_options.py`** (`package_version()`) to `X.Y.Z-dev` so runs without an editable install still report a sensible string.
3. **GitHub HTTP `User-Agent`** is built from `package_version()` in `collectors/github.py` — no separate version string to edit.
4. Add a **`CHANGELOG.md`** section `## X.Y.Z - YYYY-MM-DD` and move items out of **Unreleased** as appropriate.
5. Tagging on Git (optional): `git tag -a vX.Y.Z -m "Release X.Y.Z"` after the version commit is on the branch you intend to release.

## Not the same: JSON truth payload `version`

`--format json` output includes a **`version`** field inside the payload that describes the **truth-payload schema** (an integer contract for automation), not the PyPI package version. See `docs/V1_TAG_ANNOTATION_DRAFT.md` and `docs/CLI_FIRST_V1_RELEASE_CHECKLIST.md`.
