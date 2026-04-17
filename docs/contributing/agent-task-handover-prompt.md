# Agent handover prompt — release candidate and onboarding work

Copy everything under **“Prompt (copy from here)”** into any AI agent (Claude, Codex, Cursor, etc.). Keep PR titles and GitHub descriptions in **English** (see `CONTRIBUTING.md`).

**How this lands in the repo:** via a normal branch and PR into `main` — not a direct push to `main` (branch protection). Until merged, you can still paste the prompt from this file on `main` in the web UI or from any branch checkout.

---

## Prompt (copy from here)

**Role**  
You work in the **timelog-extract** repository (CLI entry point `gittan`, product name Gittan). Read `README.md`, `docs/product/v1-scope.md`, and `docs/runbooks/versioning.md`. Inspect existing setup and diagnostics code (`core/global_timelog_setup_lib.py`, `core/cli_global_timelog_setup.py`, `core/cli_doctor_sources_projects.py`). Respect **local-first** behavior: do not add mandatory cloud upload paths for user data.

**Primary goal (product)**  
Deliver **easier project setup**: fewer manual steps from install to a useful first run, clearer errors, and obvious next actions. **Before writing new systems:** discover what already exists — e.g. `gittan setup`, `gittan doctor`, and reporting flags that already summarize environment, sources, or patterns. Prefer **composing or strengthening** existing commands into one well-documented path rather than duplicating behavior.

**Optional idea (not a requirement)**  
The maintainer may want **AI-assisted** explanations or suggestions inside the tool. Treat this as **optional**: do **not** add an LLM integration unless it clearly adds value beyond existing CLI behavior. Prefer simplicity and transparency.

**Release candidate deliverable**  
Prepare the **next release candidate** per `docs/runbooks/versioning.md`: update `CHANGELOG.md` and version fields where required (`pyproject.toml`, `core/cli_options.py` dev fallback per checklist).

**Git tag pattern for RC (mandatory when tagging an RC)**  
When you create a **test/release tag** for this candidate, use:

```text
v<MAJOR>.<MINOR>.<PATCH>rc<NUM>-<Agent>-version
```

Examples: `v0.2.5rc1-Codex-version`, `v0.2.5rc1-Claude-version`.

- `<Agent>` = the tool or environment name (e.g. `Codex`, `Cursor`, `Claude`), **PascalCase**, no spaces.  
- The literal suffix **`-version`** is always part of the tag name.  
- Bump **`rc<NUM>`** (`rc1`, `rc2`, …) if you need another RC at the same patch level.  
- Align `<MAJOR>.<MINOR>.<PATCH>` with the intended release line. If the Python package version cannot include the agent name (PEP 440), keep the **package** version as a normal pre-release (e.g. `0.2.5rc1`) while the **git tag** still follows the pattern above — resolve consistently with `docs/runbooks/versioning.md`.

**PyPI workflow warning (important)**  
This repository’s **Publish to PyPI** workflow (`.github/workflows/pypi.yml`) runs on `push` of tags matching `v*.*.*`. That pattern **also matches** tags like `v0.2.5rc1-Codex-version`. Pushing such a tag to `origin` may **trigger the publish workflow**. Coordinate with the maintainer before pushing RC tags. The **official** release tag `vX.Y.Z` after merge to `main` is described in `docs/runbooks/versioning.md`.

**Working directory and worktrees**  
If the maintainer uses a **git worktree**, operate in the **worktree directory that has your branch checked out**, not another clone by mistake. Run `git status` and confirm you are on the intended branch before committing.

**Documented checks before you call the work “done”**  
From the repository root of that working tree:

1. `bash scripts/run_autotests.sh`  
2. `coderabbit review --base main --type committed --plain` (optional local pre-check; still subject to [CLI limits](https://docs.coderabbit.ai/cli))

**Push and pull request**  
1. `git push -u origin <your-branch>`  
2. Before `gh pr create`, run `gh pr list --head <your-branch>`. If a PR already exists for this branch, **do not** open a duplicate — update the existing PR or comment there.  
3. PR title and body in **English**.

**A/B between agents (when the maintainer compares deliveries)**  
- Do **not** merge to `main` or assume the maintainer will merge immediately.  
- Use the **same target version line** as the other agent when the comparison is intentional.  
- In the PR description, add a short **“Compared to other agent runs”** note: 3–5 bullets on what your RC changes and why.  
- The maintainer may **manually test** a previous agent’s RC before your run finishes — that is normal; do not treat it as a blocker error.

**Hard constraints**  
- Do not commit `TIMELOG.md` or `private/`.  
- Keep the diff focused; avoid unrelated refactors.  
- After changes, autotests must pass.

**Definition of done**  
1. Clear improvement or new setup/diagnostics path, minimally documented.  
2. Version/changelog updates per repo checklist; RC git tag follows `v…rcN-Agent-version` when an RC tag is created.  
3. Autotests green; branch pushed; one PR (new or existing) ready for review.

---

## Maintainer note

- **Before Codex (or another agent) starts:** you can paste the prompt from **any** revision of this file — including the version on `main` in the GitHub web UI — without waiting for a merge. Merging this doc PR only makes the canonical text live in the default branch for everyone.  
- **Landing the doc:** open a PR from branch `docs/agent-rc-handover-prompt` (or recreate it from `main`) and merge when ready.
