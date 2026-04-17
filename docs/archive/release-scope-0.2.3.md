# Release 0.2.3 — planned scope

**Intent:** first **PyPI** distribution milestone so installers can run `pip install timelog-extract` / `gittan` without cloning. **0.2.2** shipped setup safety, Pages assets, and related docs; **0.2.3** is the numbered cut for packaging automation + initial upload.

## Must ship (0.2.3)

- Bump `[project] version` in `pyproject.toml` to **0.2.3** and `package_version()` fallback in `core/cli_options.py` to `0.2.3-dev`. **Done** in `release/0.2.3`.
- **Build and upload** sdist + wheel: workflow [`.github/workflows/pypi.yml`](../.github/workflows/pypi.yml) (trusted publishing). Maintainer must register the PyPI project + trusted publisher, then tag **`v0.2.3`** or run the workflow manually.
- **Smoke** after upload: `pip install timelog-extract`, `timelog-extract -V`, `gittan -V`; CI **package** job approximates install-from-wheel on every PR.
- **`CHANGELOG.md`**: section `## 0.2.3 - YYYY-MM-DD` with publish notes. **Done** in `release/0.2.3`.

## Should (same release if feasible)

- **Active project config** living outside the repo (e.g. under `~/.gittan/`) with a documented migration from repo-root `timelog_projects.json` — reduces gitignored-data incidents (see `docs/incidents/2026-04-13-project-config-backup-gap.md`).
- Optional **`gittan config export` / `gittan config import`** (thin wrappers around copy + validate) if migration lands in 0.2.3; otherwise defer to 0.2.4.

## Nice / follow-up

- Further **terminal table consistency** beyond `gittan status` / `gittan doctor` (see `docs/terminal-style-guide.md`).
- **Homebrew** or other installers — only after PyPI is stable; track separately from this scope doc.
- **Brand / visuals:** Canonical `docs/brand/gittan-brand-mark.png` + `gittan-og-card.png`; `drafts/` / `archive/`; derived **`gittan-logo.png`** (site), favicon, README icon, `og-image.png`; optional GitHub **Social preview** from `repository-open-graph-template.png`. See `docs/brand/README.md` and `scripts/build_brand_assets.sh`.

## References

- Maintainer checklist: [`docs/versioning.md`](VERSIONING.md)
- Incident that informed config backup + agent rules: [`docs/incidents/2026-04-13-project-config-backup-gap.md`](incidents/2026-04-13-project-config-backup-gap.md)
