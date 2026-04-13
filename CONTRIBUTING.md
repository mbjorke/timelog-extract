# Contributing

Thanks for helping improve Timelog Extract / Gittan. This document is the single entry point for contributors; agent-specific habits (timelog files, worktrees) live in [`AGENTS.md`](AGENTS.md).

**`main` is branch-protected** — no direct pushes; use a branch and PR. See [`BRANCH.md`](BRANCH.md) and [`docs/CI.md`](docs/CI.md) for workflow and what CI runs.

## Pull requests

- **Write the PR title and PR description in English.** That is required for reviewers and tools (e.g. CodeRabbit). See [`AGENTS.md`](AGENTS.md).
- Prefer **Draft** PRs while iterating; mark **Ready for review** when CI is green and the scope is stable.
- Keep changes focused. Split unrelated work into separate PRs or branches when possible.

## Development setup

- Python **3.9+** (CI uses 3.11).
- Install in editable mode from the repository root:

  ```bash
  python3 -m pip install -e .
  ```

- Run the same checks as CI:

  ```bash
  bash scripts/run_autotests.sh
  ```

  This runs the line-length policy (`scripts/check_file_lengths.py`, default max **500** lines per Python file) and the unit tests under `tests/`.

- For a quicker test loop:

  ```bash
  python3 -m unittest discover -s tests -p "test_*.py"
  ```

## Code style and structure

- Match existing patterns in the touched modules (imports, typing, error handling).
- If a file approaches the line limit, **split by responsibility** rather than raising the limit (see `README.md` “File Size Policy”).
- Do **not** commit local timelog files (`TIMELOG.md` is gitignored by policy).

## Cursor extension

If you change `cursor-extension/`, run `npm install` and `npm run build` there (mirrors the `extension` job in CI).

## Releases and versioning

The installable **package version** lives in `pyproject.toml` and is shown by `gittan -V` / `timelog-extract -V`. When you cut a release or bump that number, follow the checklist in **[`docs/VERSIONING.md`](docs/VERSIONING.md)** (including `CHANGELOG.md` and the dev fallback in `core/cli_options.py`).

## License

Copyright © Blueberry Maybe AB. The project is distributed under **[GNU GPL-3.0-or-later](LICENSE)**.

For background on the license direction, see **`docs/LICENSE_GOALS.md`**.
