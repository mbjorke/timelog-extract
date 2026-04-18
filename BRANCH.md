# Branching model (`main` + short-lived `task/*`)

The **default branch** on GitHub is **`main`**. It is **branch-protected**: no direct pushes; changes land via pull requests. CI runs on PRs (see `docs/runbooks/ci.md`).

There is **no standing integration branch** named `dev` on `origin` — day-to-day work merges into **`main`** when ready.

## Recommended workflow

1. Sync:
   - `git fetch origin`
   - `git switch main && git pull origin main`
2. Create a short-lived branch from **`main`**:
   - `git switch -c task/<short-scope> main`
3. Implement a small-scoped change, run tests, commit, push.
4. Open PR **`task/<short-scope> -> main`**.
5. Merge and **delete the task branch** immediately (local + remote).

## Review intent

- **`task/* -> main`:** feature, docs, and incremental review in one step. Keep PRs narrow so review stays light.

## Release flow

- **Normal path:** merge work to **`main`**, then tag from **`main`** when releasing (see `docs/runbooks/versioning.md`).
- Use **`release/X.Y.Z`** only when you need explicit isolation for version bumps (`pyproject.toml`, `CHANGELOG.md`, packaging chores).
- Before version edits, verify branch intent: `git branch --show-current`

## Branch hygiene rules

- Prefer ephemeral branch names: `task/*`.
- Avoid long-lived branch families unless explicitly required:
  - `feat/*`, `fix/*`, `docs/*`, `cursor/*`.
- Keep PR scope narrow and merge quickly to reduce drift.

## Naming migration note

- Treat `rc-*` feature naming as legacy.
- Use `task/*` for new implementation work.
- Keep `release/X.Y.Z` only for explicit release isolation.
- Documentation/process artifacts still using `rc-` should be renamed gradually to `task-` equivalents as they are touched.

## If a separate `dev` branch exists again (forks / policy change)

A long-lived second line (often called `dev`) can **diverge** from `main`. Do **not** “wing it” in the merge UI — follow **`docs/runbooks/dev-main-alignment.md`** and use **`docs/task-prompts/dev-main-alignment-handoff.md`** when you need a careful reset or handoff.

## Agents

- **Never push directly to `main`**.
- Default: short-lived **`task/*` branches from `main`**, PR into **`main`**.
- For release/version operations, follow `AGENTS.md` and `docs/runbooks/versioning.md`.
