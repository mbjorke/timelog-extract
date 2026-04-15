# Daily Repo Hygiene Routine

Status: Active routine
Cadence: Daily (start or end of workday)
Owner: Maintainer or active agent

## Purpose

Keep release branches merge-ready, reduce review loops, and prevent "hidden drift"
in docs/config/process files.

## 10-15 minute routine

1. **Branch and drift check (2 min)**
   - `git branch --show-current`
   - `git status --short`
   - Confirm you are on the intended branch (`release/X.Y.Z` for release work).

2. **Main sync check (2 min)**
   - `git fetch origin`
   - If release branch: check whether `origin/main` has moved and merge early.

3. **Uncommitted scope sanity (2 min)**
   - Group changes by intent:
     - feature/code
     - docs/reorg
     - config/local-only
   - Avoid mixed "everything commits".

4. **Validation loop (3-5 min)**
   - Run targeted test for changed area.
   - Then run `./scripts/run_autotests.sh` when scope is meaningful.

5. **Docs/link hygiene (1-2 min)**
   - Ensure moved/renamed docs still have valid references.
   - Keep docs in correct folders:
     - `docs/decisions`, `docs/roadmap`, `docs/ideas`, `docs/specs`, `docs/rc-prompts`, `docs/archive`.

6. **Local safety guard (1 min)**
   - Verify no accidental destructive handling of `timelog_projects.json`.
   - Ensure `TIMELOG.md` and local private notes are not staged.

## End-of-day release branch checklist

- [ ] `release/*` branch is synced with latest `origin/main` (or consciously deferred).
- [ ] Work is committed in logical chunks.
- [ ] Tests are green for committed scope.
- [ ] RC prompt/spec updated if scope changed.
- [ ] Next action is explicit (continue, review, or ready for PR).

## Escalation rule

If routine finds >3 unrelated change clusters or uncertain branch/version scope:

1. Stop coding.
2. Write a short "state snapshot" note in PR/branch context.
3. Split work or create follow-up branch before continuing.
