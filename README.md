<div align="center">

<img src="https://raw.githubusercontent.com/mbjorke/timelog-extract/main/gittan-readme-icon.png" width="128" height="128" alt="Gittan logo" />

# Gittan

### Timelog Extract

**Local time reports from how you actually work.**

Aggregate IDE, browser, mail, and worklog signals—plus optional GitHub activity—into **project hours** and optional **invoice PDFs**.  
Core reporting is **local-first**; there is no built-in cloud upload path.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue?style=for-the-badge)](LICENSE)
[![PyPI package](https://img.shields.io/badge/pypi-timelog--extract-006DAD?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/timelog-extract/)

---

## Install

**Requirements:** Python **3.9+**. You do **not** need a PyPI account to install—only maintainers need PyPI access to publish.  
If the shell says `command not found: pip`, use **`python3 -m pip`** instead of a bare `pip` command (common on macOS).

### Recommended: **pipx** (macOS / Linux — keeps `gittan` on your PATH)

`pip install --user` puts scripts under `~/Library/Python/…/bin` (macOS), which is **often not on PATH**, so `gittan` can look “missing” until you edit shell config. **pipx** installs CLI tools into `~/.local/bin` and is easier to get right:

```bash
brew install pipx
pipx ensurepath
```

**Important:** open a **new terminal tab**, or run `source ~/.zshrc`, so `PATH` picks up `pipx ensurepath`. Then:

```bash
pipx install timelog-extract
gittan -V
```

### Alternative: **pip install --user** (PyPI)

```bash
python3 -m pip install --user timelog-extract
```

Add the user script directory to **PATH** (macOS example — version may differ):

```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
```

Put that line in `~/.zshrc` (or run `gittan doctor` — it will hint if it detects this issue).

<sub>Until PyPI has the package for your environment, use **from source** below.</sub>

<br/>

<details>
<summary><b>More install options</b></summary>

<div align="left">

**Virtual environment**

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install timelog-extract
```

**From source** <span id="from-source"></span>

```bash
git clone https://github.com/mbjorke/timelog-extract.git
cd timelog-extract
python3 -m pip install -e .
```

Verify:

```bash
gittan --help
gittan -V
```

Publishing checklist: [`docs/VERSIONING.md`](docs/VERSIONING.md).

</div>
</details>

<br/>

</div>

## Get started

1. **Health check** — from a git repo that should have (or will have) a worklog:
   ```bash
   gittan doctor
   ```
   `gittan doctor` ends with the most useful next command to run for your current setup.
2. **First-time setup** — wizard for environment, optional global `TIMELOG.md` hooks, and `timelog_projects.json`:
   ```bash
   gittan setup --dry-run    # preview
   gittan setup              # interactive
   ```
   `gittan setup` now closes with copyable next steps so the first real report is obvious.
3. **First report** — today’s activity:
   ```bash
   gittan report --today --source-summary
   ```

`TIMELOG.md` in the **repository root** (where you run the command) is the default worklog unless you pass `--worklog` or set a path in config. See **Timelog vs config** below.

---

## Everyday commands

| Goal | Command |
|------|---------|
| Full report (prompts for range if you omit dates) | `gittan report` |
| Today / last week / custom range | `gittan report --today` · `--last-week` · `--from 2026-04-01 --to 2026-04-30` |
| Quick hours overview | `gittan status --today` |
| Source mix / empty collectors | `gittan sources` (and `docs/SOURCES_AND_FLAGS.md`) |
| Edit projects JSON | `gittan projects` |
| Machine-wide commit → `TIMELOG.md` hooks | `gittan setup-global-timelog` |

**JSON or HTML export** (quiet, script-friendly):

```bash
gittan report --today --format json
gittan report --from 2026-04-01 --to 2026-04-30 --format json --json-file out/truth.json --report-html out/report.html
```

**Optional GitHub activity:** set `GITHUB_USER` or `--github-user`; optional `GITHUB_TOKEN` for rate limits. Details: `docs/SOURCES_AND_FLAGS.md`.

---

## What else is in the repo

- **Cursor extension** (companion, beta) — `cursor-extension/README.md`.
- **Engine script** (same API as the extension): `python3 scripts/run_engine_report.py --today --pdf`.

---

## Timelog vs config

- **`TIMELOG.md`** — human-readable work journal; safe to treat as a diary.
- **`timelog_projects.json`** — machine config; **back it up** (e.g. under `~/.gittan/`). Setup creates timestamped backups before replacing invalid JSON.

---

## Troubleshooting

| Issue | Where to look |
|--------|----------------|
| `command not found: gittan` after install | Install via **pipx** (above), or add `~/Library/Python/…/bin` and `~/.local/bin` to **PATH**; run **`gittan doctor`** for copy-paste hints. |
| “0 events” / sources empty | `docs/SOURCES_AND_FLAGS.md` |
| Missing deps / editable install | `python3 -m pip install -e .` from clone |
| Invalid project config | `gittan setup`; backups named `timelog_projects.backup-*.json` |
| Paths / permissions | `--worklog`, browser DBs, Mail / Screen Time access |
| Global timelog automation | `gittan setup-global-timelog`, `GLOBAL_TIMELOG_AUTOMATION.md` |

---

## Feedback

Questions, install friction, or “does this match your workflow?” — use **[GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions)** (e.g. **General** or **Q&A**). For **bugs** or small reproducible issues, open an **[issue](https://github.com/mbjorke/timelog-extract/issues)** instead.

---

## Documentation map

Vision, privacy, CLI flags, style, and release checklists live under **`docs/`**. Start with **[`docs/VISION_DOCUMENTS.md`](docs/VISION_DOCUMENTS.md)** for an index (e.g. `SOURCES_AND_FLAGS.md`, `PRIVACY_SECURITY.md`, `TERMINAL_STYLE_GUIDE.md`, `CLI_FIRST_V1_RELEASE_CHECKLIST.md`).

---

## Contributing · tests · license

- **[`CONTRIBUTING.md`](CONTRIBUTING.md)** — PR titles/descriptions in **English**; run tests before pushing.
- **Maintainers (repo hygiene):** issue templates, Discussions, **Social preview** in GitHub Settings; **brand** — canonical PNGs in `docs/brand/`, then [`scripts/build_brand_assets.sh`](scripts/build_brand_assets.sh) → root **`gittan-logo.png`** (site), favicon, README icon, `og-image.png`. See [`docs/brand/README.md`](docs/brand/README.md), [`docs/OPPORTUNITIES.md`](docs/OPPORTUNITIES.md).
- **`main` is branch-protected** — use a branch and PR; see **[`BRANCH.md`](BRANCH.md)** and **[`docs/CI.md`](docs/CI.md)**.
- Tests: `./scripts/run_autotests.sh` (also enforced in CI).
- **License:** GNU **GPL-3.0-or-later** — [`LICENSE`](LICENSE). Changelog: [`CHANGELOG.md`](CHANGELOG.md).
