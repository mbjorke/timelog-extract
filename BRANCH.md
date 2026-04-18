# Branching model (`main` + `dev`)

The repository uses two protected branches on GitHub:

- `dev`: protected integration branch for `task/*` work.
- `main`: protected release/integration branch.

Direct pushes are blocked on both; changes land via pull requests. CI runs on PRs (see `docs/runbooks/ci.md`).

Use a two-level flow:

- `main`: release-ready history only.
- `dev`: integration branch for ongoing agent work.

## Recommended workflow

1. Sync base branches:
   - `git fetch origin`
   - `git switch main && git pull origin main`
   - `git switch dev && git pull origin dev` (if `dev` exists)
2. Create a short-lived task branch from `dev`:
   - `git switch -c task/<short-scope> dev`
3. Implement a small-scoped change, run tests, commit, push.
4. Open PR `task/<short-scope> -> dev`.
5. Merge and **delete task branch** immediately (local + remote).
6. When `dev` is stable, open PR `dev -> main`.

## Review intent by branch

- `task/* -> dev`: feature/incremental review.
- `dev -> main`: release/integration review (final quality gate before release).

## Release flow

- Normal release path: **`dev -> main`**, then tag from `main`.
- Use `release/X.Y.Z` only when you need explicit isolation for:
  - version bump files (`pyproject.toml`, `CHANGELOG.md`, release chores),
  - packaging/publish handoff steps.
- Before version edits, always verify branch intent:
  - `git branch --show-current`

## Branch hygiene rules

- Prefer ephemeral branch names: `task/*`.
- Avoid long-lived branch families unless explicitly required:
  - `feat/*`, `fix/*`, `docs/*`, `cursor/*`.
- Keep PR scope narrow and merge quickly to reduce cross-branch drift.

## Naming migration note

- Treat `rc-*` feature naming as legacy.
- Use `task/*` for new implementation work.
- Keep `release/X.Y.Z` only for explicit release isolation.
- Documentation/process artifacts still using `rc-` should be renamed gradually to `task-` equivalents as they are touched.

## Agents

- **Never push directly to `main`**.
- Default agent target is `dev` via short-lived `task/*` branches.
- For release/version operations, follow `AGENTS.md` and `docs/runbooks/versioning.md`.