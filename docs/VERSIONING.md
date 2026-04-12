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

## PyPI distribution (planned)

The project is already a normal **setuptools** package (`pyproject.toml`, `[project] name = "timelog-extract"`), but it is **not** published to [PyPI](https://pypi.org/) yet. We plan a first upload around a **0.2.3** patch release so installers can use:

```bash
pip install timelog-extract
```

without cloning the repository.

When cutting that release, extend the checklist above with:

1. **Build** sdist and wheel (e.g. `python -m build`).
2. **Upload** with `twine` or **trusted publishing** from CI, using project PyPI credentials.
3. **Smoke-test** in a clean virtualenv: `pip install timelog-extract` and `timelog-extract -V` / `gittan -V`.

## Not the same: JSON truth payload `version`

`--format json` output includes a **`version`** field inside the payload that describes the **truth-payload schema** (an integer contract for automation), not the PyPI package version. See `docs/V1_TAG_ANNOTATION_DRAFT.md` and `docs/CLI_FIRST_V1_RELEASE_CHECKLIST.md`.
