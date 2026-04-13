# Release 0.2.3 — planned scope

**Intent:** first **PyPI** distribution milestone so installers can run `pip install timelog-extract` / `gittan` without cloning. Patch **0.2.2** is the current line for incident fixes, setup safety, Pages assets, and docs; **0.2.3** is the next numbered cut aimed at publish + smoke.

## Must ship (0.2.3)

- Bump `[project] version` in `pyproject.toml` to **0.2.3** and `package_version()` fallback in `core/cli_options.py` to `0.2.3-dev`.
- **Build and upload** sdist + wheel per [Package versioning / PyPI](VERSIONING.md#pypi-distribution-planned) (build, twine or trusted publishing, credentials).
- **Smoke** in a clean virtualenv: `pip install timelog-extract`, `timelog-extract -V`, `gittan -V`, and one minimal `gittan doctor` / `gittan report` path.
- **`CHANGELOG.md`**: section `## 0.2.3 - YYYY-MM-DD` with publish notes and any last-minute fixes.

## Should (same release if feasible)

- **Active project config** living outside the repo (e.g. under `~/.gittan/`) with a documented migration from repo-root `timelog_projects.json` — reduces gitignored-data incidents (see `docs/incidents/2026-04-13-project-config-backup-gap.md`).
- Optional **`gittan config export` / `gittan config import`** (thin wrappers around copy + validate) if migration lands in 0.2.3; otherwise defer to 0.2.4.

## Nice / follow-up

- Further **terminal table consistency** beyond `gittan status` / `gittan doctor` (see `docs/TERMINAL_STYLE_GUIDE.md`).
- **Homebrew** or other installers — only after PyPI is stable; track separately from this scope doc.

## References

- Maintainer checklist: [`docs/VERSIONING.md`](VERSIONING.md)
- Incident that informed config backup + agent rules: [`docs/incidents/2026-04-13-project-config-backup-gap.md`](incidents/2026-04-13-project-config-backup-gap.md)
