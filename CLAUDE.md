# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

If this file conflicts with `AGENTS.md`, follow `AGENTS.md` as the source of truth.

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

- `**timelog_extract.py**` — top-level module; re-exports from `core/` for backward-compat; also the `__main__` entrypoint when run directly.
- `**core/cli.py**` — wires up the Typer app by importing CLI command modules as side effects (`cli_doctor_sources_projects`, `cli_global_timelog_setup`, `cli_report_status`, `cli_review`). Each of those registers its own subcommand on the shared `app` in `core/cli_app.py`.
- `**scripts/run_engine_report.py**` — standalone script using the same API as the Cursor extension.

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

Current sources (in `core/sources.py`): Claude Code CLI, Claude Desktop, Claude.ai (web), Gemini (web), Cursor, Cursor checkpoints, Codex IDE, Gemini CLI, TIMELOG.md, Apple Mail, Chrome, Lovable (desktop), GitHub.

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

- Fast rule-of-thumb:
  - never push to `main`
  - use `release/X.Y.Z` for release-bound work
  - PR title/description in English
- Canonical policy lives in `AGENTS.md` (branch/release/review sections).
- Detailed release flow: `docs/VERSIONING.md`.

### Timelog file rules (critical)

- Do not commit `TIMELOG.md`, `timelog_projects.json`, or anything under `private/`.
- Treat `timelog_projects.json` as critical local data; never move/delete without confirmation or backup.
- Use real wall time (`date '+%Y-%m-%d %H:%M'`) for timelog entries.
- Canonical safety/review cadence rules live in `AGENTS.md`.

## CI jobs (`.github/workflows/ci.yml`)


| Job         | What it does                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------ |
| `python`    | Installs (editable), smoke-runs `timelog_extract.py --today`, enforces 500-line limit, runs unit tests |
| `package`   | Builds sdist + wheel (`python -m build`), smoke-installs wheel, checks `gittan -V`                     |
| `extension` | `npm install && npm run build` in `cursor-extension/`                                                  |


GitHub Pages deploys only on push to `main` (see `docs/CI.md`).