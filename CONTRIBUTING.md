# Contributing

Thanks for helping improve Timelog Extract / Gittan. This document is the single entry point for contributors; agent-specific habits (timelog files, worktrees) live in [`AGENTS.md`](AGENTS.md).

**`main` is branch-protected** — no direct pushes; use a branch and PR.  
Default contributor flow is **`task/* -> dev -> main`**. See [`BRANCH.md`](BRANCH.md) and [`docs/ci.md`](docs/ci.md) for CI and merge flow.

## User feedback (not code)

Experience reports, setup confusion, and product questions belong in **[GitHub Discussions](https://github.com/mbjorke/timelog-extract/discussions)** so others can find them. Use **issues** for defects or concrete feature requests you can describe precisely.

## Pull requests

- **Write the PR title and PR description in English.** That is required for reviewers and tools (e.g. CodeRabbit). See [`AGENTS.md`](AGENTS.md).
- Prefer **Draft** PRs while iterating; mark **Ready for review** when CI is green and the scope is stable.
- Keep changes focused. Split unrelated work into separate PRs or branches when possible.

## Branch and naming conventions

1. Start from `dev`:
   - `git fetch origin`
   - `git switch dev`
   - `git pull origin dev`
2. Create a short-lived branch: `task/<short-scope>`
   - Example: `task/doctor-github-note`
3. Open PR into `dev` (not directly into `main`, except maintainers for explicit release work).
4. After merge, delete the task branch (local and remote).

Naming notes:

- `task/*` is the default for new work.
- `rc-*` naming is legacy for feature work and should not be used for new contributor branches.
- `release/X.Y.Z` is reserved for explicit release isolation/versioning chores.

## Development setup

- Python **3.9+** (CI uses 3.11).
- Install in editable mode from the repository root:

  ```bash
  python3 -m pip install -e .
  ```

- Run the same checks as CI **before you push** (agents: see `AGENTS.md` fast-path step 6 and `.cursor/rules/pre-push-quality-gate.mdc`):

  ```bash
  bash scripts/run_autotests.sh
  ```

  This runs the line-length policy (`scripts/check_file_lengths.py`, default max **500** lines per Python file) and the unit tests under `tests/`.

- **Optional:** install a local **pre-push** hook so a failed run blocks `git push` — see [`scripts/git-hooks/README.md`](scripts/git-hooks/README.md).

- For a quicker test loop:

  ```bash
  python3 -m unittest discover -s tests -p "test_*.py"
  ```

## Code style and structure

- Match existing patterns in the touched modules (imports, typing, error handling).
- If a file approaches the line limit, **split by responsibility** rather than raising the limit (see `README.md` “File Size Policy”).
- Do **not** commit local timelog files (`TIMELOG.md` is gitignored by policy).
- Do **not** commit local backup/config artifacts (for example `timelog_projects*.json` generated during local experimentation).

## Cursor extension

If you change `cursor-extension/`, run `npm install` and `npm run build` there (mirrors the `extension` job in CI).

## Releases and versioning

The installable **package version** lives in `pyproject.toml` and is shown by `gittan -V` / `timelog-extract -V`. When you cut a release or bump that number, follow the checklist in **[`docs/versioning.md`](docs/versioning.md)** (including `CHANGELOG.md` and the dev fallback in `core/cli_options.py`).

## License

Copyright © Blueberry Maybe AB. The project is distributed under **[GNU GPL-3.0-or-later](LICENSE)**.

For background on the license direction, see **`docs/license-goals.md`**.
