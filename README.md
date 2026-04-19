<div align="center">

<img src="https://raw.githubusercontent.com/mbjorke/timelog-extract/main/gittan-readme-icon.png" width="128" height="128" alt="Gittan logo" />

# Gittan

### Timelog Extract

**Local time reports from how you actually work.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue?style=for-the-badge)](LICENSE)
[![PyPI package](https://img.shields.io/badge/pypi-timelog--extract-006DAD?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/timelog-extract/)

</div>

Your day leaves traces—IDE, browser, mail, commits, worklog. **Gittan** turns those signals into **project hours** and optional **invoice PDFs**, without sending your raw activity to our servers by default. Everything runs **local-first**; you stay in control.

---

## Install

You need **Python 3.9+**. If `pip` is awkward on your machine, prefer **`python3 -m pip`** (common on macOS).

**Fast path:** install the CLI with **[pipx](https://pypa.github.io/pipx/)** so `gittan` is on your PATH:

```bash
brew install pipx && pipx ensurepath
# open a new shell, then:
pipx install timelog-extract
gittan -V
```

<details>
<summary><b>Other install paths</b></summary>

**`pip install --user`** — scripts may land outside your default PATH. Add the user-level `bin` for that Python install (OS-specific; `python3 -m site --user-base` helps locate it), or run **`gittan doctor`** after install for hints.

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

Use a git checkout (usually the **repo root**) so `TIMELOG.md` lands where you expect:

1. **`gittan doctor`** — see what collectors can see on this machine.  
2. **`gittan setup`** — wire optional hooks and `timelog_projects.json` (`--dry-run` / `--interactive` if you want previews).  
3. **`gittan report --today --source-summary`** — your first real report from real traces.

By default, **`TIMELOG.md`** follows the **working directory** you run from—most often the **repository root**. Same rule as [`AGENTS.md`](AGENTS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md); override with `--worklog` or config when you need to.

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

`out/` is local output (gitignored by default). **Optional GitHub activity:** set `GITHUB_USER` / `--github-user`, optional `GITHUB_TOKEN` — details in [`docs/sources/sources-and-flags.md`](docs/sources/sources-and-flags.md).

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

Layered docs so you can go shallow or deep:

- **Find any category of doc** — [`docs/README.md`](docs/README.md) is the map.  
- **See how vision, scope, and metrics fit together** — [`docs/product/vision-documents.md`](docs/product/vision-documents.md).  
- **Use the Cursor companion (optional)** — [`cursor-extension/README.md`](cursor-extension/README.md).  
- **Call the same engine from a script** — `python3 scripts/run_engine_report.py --today --pdf`.

---

## Contributing · tests · license

If you want to change the tool, **start with [`CONTRIBUTING.md`](CONTRIBUTING.md)** — it covers branch names, **English** PR titles and descriptions, and what to run locally before review.

- **Branch like this:** short-lived `task/<scope>` from **`main`**, then open a PR — spelled out in [`BRANCH.md`](BRANCH.md).  
- **Understand CI:** what GitHub runs on every push is in [`docs/runbooks/ci.md`](docs/runbooks/ci.md).  
- **Match CI before you push:** `bash scripts/run_autotests.sh` from the **repository root**.  
- **Deeper rules for humans and agents:** [`AGENTS.md`](AGENTS.md) — timelog policy, push gates, review cadence.  
- **License:** [GNU GPL-3.0-or-later](LICENSE) — copyleft; share improvements on the same terms.  
- **What shipped when:** [`CHANGELOG.md`](CHANGELOG.md).  
- **Logos, favicon, social preview:** [`docs/brand/README.md`](docs/brand/README.md) for maintainers building assets from canonical marks.

---

## Feedback

**Questions and rough edges** → [GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions). **Bugs you can reproduce** → [Issues](https://github.com/mbjorke/timelog-extract/issues).
