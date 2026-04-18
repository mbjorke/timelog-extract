<div align="center">

<img src="https://raw.githubusercontent.com/mbjorke/timelog-extract/main/gittan-readme-icon.png" width="128" height="128" alt="Gittan logo" />

# Gittan

### Timelog Extract

**Local time reports from how you actually work.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue?style=for-the-badge)](LICENSE)
[![PyPI package](https://img.shields.io/badge/pypi-timelog--extract-006DAD?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/timelog-extract/)

</div>

Aggregate IDE, browser, mail, and worklog signals—plus optional GitHub activity—into **project hours** and optional **invoice PDFs**. Reporting is **local-first**; there is no built-in cloud upload path.

---

## Install

**Requires Python 3.9+.** If `pip` is missing or confusing on your system, use **`python3 -m pip`** (common on macOS).

**Recommended:** install the CLI with **[pipx](https://pypa.github.io/pipx/)** so `gittan` lands on your PATH:

```bash
brew install pipx && pipx ensurepath
# open a new shell, then:
pipx install timelog-extract
gittan -V
```

<details>
<summary><b>Other install paths</b></summary>

**`pip install --user`** — scripts may land outside your default PATH. Add the user-level `bin` directory for that Python install (OS-specific; `python3 -m site --user-base` helps locate it), or run **`gittan doctor`** after install for hints.

```bash
python3 -m pip install --user timelog-extract
```

**Virtualenv**

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install timelog-extract
```

**From source**

```bash
git clone https://github.com/mbjorke/timelog-extract.git
cd timelog-extract
python3 -m pip install -e .
gittan -V
```

Maintainers: release steps — [`docs/runbooks/versioning.md`](docs/runbooks/versioning.md).

</details>

---

## First run

Run these from a git checkout where you want a worklog (or any folder once you know what you’re doing):

1. **`gittan doctor`** — see what the tool can see on your machine.
2. **`gittan setup`** — optional hooks and `timelog_projects.json` (use `--dry-run` or `--interactive` if you prefer).
3. **`gittan report --today --source-summary`** — first real report.

Default worklog is **`TIMELOG.md`** in the **working directory** where you run the command (for everyday project use, that is usually the **repository root**). Same rule as [`AGENTS.md`](AGENTS.md) / [`CONTRIBUTING.md`](CONTRIBUTING.md): override with `--worklog` or config when needed.

---

## Commands you’ll use

| Goal | Command |
|------|---------|
| Interactive report (asks for dates if you omit them) | `gittan report` |
| Today / last week / range | `gittan report --today` · `--last-week` · `--from YYYY-MM-DD --to YYYY-MM-DD` |
| Clean up uncategorized time | `gittan review --today --uncategorized` |
| Quick totals | `gittan status --today` |
| Collector status | `gittan sources` |
| Edit project rules | `gittan projects` |
| Repo-wide git → worklog hooks | `gittan setup-global-timelog` |

**JSON / HTML export** (for scripts or archiving):

```bash
gittan report --today --format json
gittan report --from YYYY-MM-DD --to YYYY-MM-DD --format json --json-file out/truth.json --report-html out/report.html
```

`out/` is local output (gitignored by default). **Optional GitHub activity:** `GITHUB_USER` / `--github-user`, optional `GITHUB_TOKEN` — see [`docs/sources/sources-and-flags.md`](docs/sources/sources-and-flags.md).

---

## Timelog vs config

| | |
|--|--|
| **`TIMELOG.md`** | Human-readable journal; safe to treat as a diary. |
| **`timelog_projects.json`** | Machine rules; **back it up**. Setup writes timestamped backups before replacing broken JSON. |

---

## Troubleshooting

| Symptom | Where to look |
|--------|----------------|
| `gittan` not found | PATH (pipx `~/.local/bin`, or pip `--user` bin); then **`gittan doctor`**. |
| No events / empty sources | [`docs/sources/sources-and-flags.md`](docs/sources/sources-and-flags.md) |
| Bad or missing config | `gittan setup` · backups `timelog_projects.backup-*.json` |
| Permissions / paths | `--worklog`, browser DB access, Mail / Screen Time |
| Global hooks | [`docs/runbooks/global-timelog-setup.md`](docs/runbooks/global-timelog-setup.md) |

---

## Documentation

- **Index of all doc categories:** [`docs/README.md`](docs/README.md)  
- **Product and vision index:** [`docs/product/vision-documents.md`](docs/product/vision-documents.md)  
- **Cursor extension (optional):** [`cursor-extension/README.md`](cursor-extension/README.md)  
- **Engine script (same API as the extension):** `python3 scripts/run_engine_report.py --today --pdf`

---

## Contributing · tests · license

- **[`CONTRIBUTING.md`](CONTRIBUTING.md)** — branches, PR language (**English**), how to run checks.  
- **`main` is protected** — use a PR; see [`BRANCH.md`](BRANCH.md) and [`docs/runbooks/ci.md`](docs/runbooks/ci.md).  
- **Tests (same as CI):** `bash scripts/run_autotests.sh` from the **repository root**.  
- **License:** [GNU GPL-3.0-or-later](LICENSE) · **Changelog:** [`CHANGELOG.md`](CHANGELOG.md). Brand assets for maintainers: [`docs/brand/README.md`](docs/brand/README.md).

---

## Feedback

**Ideas and setup questions:** [GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions). **Bugs** (reproducible): [Issues](https://github.com/mbjorke/timelog-extract/issues).
