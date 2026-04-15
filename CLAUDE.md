# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Gittan** (`timelog-extract` on PyPI) is a local-first CLI tool that aggregates IDE, browser, mail, and worklog activity into project-hour reports and optional invoice PDFs. The CLI command is `gittan`; the package is installed via `pip install timelog-extract`. Python 3.9+ required.

## Commands

### Development setup

```bash
python3 -m pip install -e .   # editable install from repo root
```

### Running tests (full CI suite)

```bash
bash scripts/run_autotests.sh
```

This runs two things:
1. `python scripts/check_file_lengths.py --max-lines 500` — enforces a **500-line limit per Python file**
2. `python3 -m unittest discover -s tests -p "test_*.py"`

### Running a single test

```bash
python3 -m unittest tests/test_core_domain.py
python3 -m unittest tests/test_engine_api.py::TestEngineApi::test_some_method
```

### CLI smoke test

```bash
gittan --today --screen-time off --source-summary
python timelog_extract.py --today --screen-time off --source-summary
```

### Build package (for release validation)

```bash
python -m pip install "build>=1.0.0"
python -m build
```

### Cursor extension (if changed)

```bash
cd cursor-extension && npm install && npm run build
```

## Architecture

### Entry points

- **`timelog_extract.py`** — top-level module; re-exports from `core/` for backward-compat; also the `__main__` entrypoint when run directly.
- **`core/cli.py`** — wires up the Typer app by importing CLI command modules as side effects (`cli_doctor_sources_projects`, `cli_global_timelog_setup`, `cli_report_status`, `cli_review`). Each of those registers its own subcommand on the shared `app` in `core/cli_app.py`.
- **`scripts/run_engine_report.py`** — standalone script using the same API as the Cursor extension.

### Core data flow

```
CLI command (Typer)
  → core/report_service.py::run_timelog_report()      # orchestrator
      → core/report_runtime.py::build_run_context()   # args/config/dates
      → core/report_runtime.py::collect_runtime_events()
          → core/pipeline.py::collect_all_events()    # fan-out to all collectors
              → collectors/*.py                        # one per source
          → core/collector_registry.py                 # builds CollectorSpec list
      → core/report_aggregate.py::aggregate_report()  # dedup, group, session math
          → core/domain.py                             # classify_project, compute_sessions, etc.
          → core/analytics.py                          # group_by_day, estimate_hours_by_day
  → ReportPayload (dataclass)
      → outputs/terminal.py   # CLI display
      → outputs/pdf.py        # invoice PDF via reportlab
      → outputs/narrative.py  # executive narrative text
      → core/truth_payload.py # versioned JSON dict (for extension / --format json)
```

### Extension API boundary

`core/engine_api.py` is the **stable interface** for the Cursor extension and external callers. It exposes `run_report_payload()` / `run_report_with_optional_pdf()`, which return a plain dict from `core/truth_payload.py` (version field: `TRUTH_PAYLOAD_VERSION = "1"`). External callers should import from here, not from CLI or output modules.

### Collectors (`collectors/`)

Each collector returns a list of event dicts with keys `source`, `timestamp` (datetime), `detail`, `project`. Collectors are registered in `core/collector_registry.py` as `CollectorSpec` dataclasses with `name`, `collector` callable, `enabled`, and `reason`. The pipeline in `core/pipeline.py` runs them with a Rich progress bar (or silently in `--quiet` mode).

Current sources (in `core/sources.py`): Claude Code CLI, Claude Desktop, Claude.ai (web), Gemini (web), Cursor, Cursor checkpoints, Codex IDE, Gemini CLI, TIMELOG.md, Apple Mail, Chrome, GitHub.

`AI_SOURCES` (in `core/sources.py`) is the set of sources that qualify for the shorter `min_session` floor vs `min_session_passive` for passive sources.

### Project classification (`core/domain.py`)

`classify_project(text, profiles, fallback)` scores each project profile by counting matching `match_terms` in the event detail text. Profiles come from `timelog_projects.json` (loaded by `core/config.py::load_profiles()`). The config supports both the list format (`[{...}]`) and the object format (`{"projects": [...], "worklog": "TIMELOG.md"}`).

### Session/hour calculation (`core/domain.py`)

Events close in time (default 15 min gap) are merged into sessions by `compute_sessions()`. Session hours are floored to `min_session_minutes` (AI sources) or `min_session_passive_minutes`. `billable_total_hours()` rounds up to the nearest billing unit.

### Output layer (`outputs/`)

- `terminal.py` — Rich-based CLI rendering; follow `docs/TERMINAL_STYLE_GUIDE.md` for style rules (calm/readable; semantic hierarchy; purple/neutral base; blue for source names; muted orange for values; no rainbow coloring).
- `pdf.py` — invoice PDF via reportlab.
- `narrative.py` — executive summary text block.
- `html_timeline.py` — HTML timeline export.

## Key conventions

### File size policy

**No Python file may exceed 500 lines.** This is enforced in CI via `scripts/check_file_lengths.py`. When a file nears the limit, split by responsibility rather than raising the limit.

### Branch and PR policy

- **`main` is branch-protected** — never push directly.
- Use **`release/X.Y.Z`** branches for version bumps (`pyproject.toml`, `core/cli_options.py` dev fallback, `CHANGELOG.md`). Small non-release fixes use any short-lived named branch.
- PR titles and descriptions must be in **English**.
- Keep PRs in **Draft** while iterating; mark Ready for review when CI is green.
- For version release steps, see `docs/VERSIONING.md`.
- After a squash-merge, rebase or merge `origin/main` back into an open `release/*` branch before pushing more commits (git history diverges after squash).

### Timelog file rules (critical)

- **Never commit `TIMELOG.md`** — it is gitignored by policy.
- When adding a timelog entry, use `date '+%Y-%m-%d %H:%M'` for the real wall time; do not round or invent timestamps.
- **Never commit `timelog_projects.json`** (gitignored; treat as critical user data). Before renaming/deleting, confirm with the user or take a timestamped backup first.
- Do not commit anything under `private/`.

### Local data safety

`timelog_projects.json` is the user's project config and **not recoverable from git** — it is gitignored. The config is saved atomically via `core/config.py::save_projects_config_payload()` (temp file + `os.replace`). Treat moves/deletes of this file as destructive; always confirm with the user or use a timestamped backup.

### CodeRabbit review cadence

- Push meaningful batches; trigger `@coderabbitai full review` only when the scope is complete and CI is green.
- Aim for 1-2 review cycles per PR; resolve feedback in one consolidated commit when possible.

## CI jobs (`.github/workflows/ci.yml`)

| Job | What it does |
|---|---|
| `python` | Installs (editable), smoke-runs `timelog_extract.py --today`, enforces 500-line limit, runs unit tests |
| `package` | Builds sdist + wheel (`python -m build`), smoke-installs wheel, checks `gittan -V` |
| `extension` | `npm install && npm run build` in `cursor-extension/` |

GitHub Pages deploys only on push to `main` (see `docs/CI.md`).
