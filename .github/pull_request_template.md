## Summary

## Branch flow

## Test plan

## Review close-out checklist

When responding to automated review comments (CodeRabbit, CI):

- [ ] Read **all** comments before fixing any — categorise each as fix / explain / escalate
- [ ] Consolidate fixes into **one commit**; run `bash scripts/run_autotests.sh` before pushing
- [ ] Reply to **every** open thread:
  - Fixed → `Addressed in <sha>: <what changed>`
  - Not applicable → `Not applicable — <reason>` (pre-existing, accepted trade-off, misread)
  - Needs decision → `Needs maintainer decision — <why>`
- [ ] Leave no thread silently resolved

## Checklist

- **PR title and description are in English** (required for reviewers and tools such as CodeRabbit).
- **Branch/target follows workflow** (`task/* -> main` by default; `release/*` when versioning is isolated).
- **Scope matches the branch**; unrelated changes are split out or noted.
- **`bash scripts/run_autotests.sh`** (or equivalent) passes locally when relevant.
- If the maintainer **taught a preference** worth handing off, a short TIL in [`docs/ideas/til/`](docs/ideas/til/) (same month's `YYYY-MM.md`) helps the next session; see [`AGENTS.md`](AGENTS.md) → *Maintainer TIL*.

## See also (optional)

- [`AGENTS.md`](AGENTS.md) — test gate, branches, review cadence
- [`docs/decisions/agent-review-contract.md`](docs/decisions/agent-review-contract.md) — severity → who fixes what
- [`docs/brand/values.md`](docs/brand/values.md) · [`docs/brand/identity.md`](docs/brand/identity.md) — values and visual voice when copy or UX touches users
- [`docs/ideas/team-lexicon.md`](docs/ideas/team-lexicon.md) — shorthand and TIL for human ↔ agent chat
