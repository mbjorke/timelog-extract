# rabbit-loop — CodeRabbit loop-engineering workflow

Canonical workflow for the `/rabbit-loop` skill. A **loop-engineering** pass
(Addy Osmani, https://addyosmani.com/blog/loop-engineering/): instead of
hand-prompting turn-by-turn, run a **loop** where a generator produces work, an
**independent critic** grades it against a verifiable condition, the generator
fixes within bounds, and the loop repeats until a **stopping condition** holds —
with state on disk and the human staying engaged.

The critic here is **CodeRabbit** ("kanin"), run locally via its CLI. It is a
different system from the generator, so it does not self-grade its own work.

Policy (branches, PR language, safety, tests): **`AGENTS.md`**.
Fix bounds by severity: **`docs/decisions/agent-review-contract.md`**.

## Roles (generator vs critic)

| Role | Who | Does |
|------|-----|------|
| Generator | this agent (Claude Code / Cursor) | implements the task, commits, applies in-contract fixes |
| Critic 1 | **CodeRabbit CLI** | independent review of the local diff → structured findings |
| Critic 2 | **autotests** | `scripts/run_autotests.sh` (500-line gate + unit tests) |
| Gate | **maintainer (human)** | final review; the loop never merges |

## The loop (converge-then-pause)

```
0. Setup    Work on a task/* branch from origin/main (a worktree is ideal). Base = origin/main.
1. Generate Implement the task. Commit.
2. Critic   scripts/rabbit_loop.sh            # base defaults to origin/main
              → coderabbit review --agent  (structured findings)  + scripts/run_autotests.sh
3. Triage   For each CodeRabbit finding, map severity via agent-review-contract.md:
              • in-contract (High/Medium, ≤5 tracked files, safe dirs) → fix + add/adjust tests
              • Critical / out-of-contract / broad refactor          → DO NOT auto-fix; ESCALATE
4. Apply    Make the in-contract fixes. Keep autotests green.
5. Record   Append the iteration to .rabbit-loop/state.md (findings, action, commit SHA).
6. Repeat   Go to 2 until CONVERGED, or hit the iteration cap, or only escalations remain.
7. Human    Hand back the converged diff + the escalation list for maintainer review.
```

### Stopping condition (the `/goal`)

**CONVERGED** = CodeRabbit reports no actionable in-contract findings **and**
`scripts/run_autotests.sh` passes. `scripts/rabbit_loop.sh` prints a machine
trailer — `RABBIT_LOOP: CONVERGED` (exit 0) or `RABBIT_LOOP: ITERATE` (exit 1)
— and exits 2 on a setup problem (e.g. not authenticated).

### Guardrails (stay engaged; avoid comprehension debt)

- **Iteration cap: default 3.** Unattended loops compound mistakes and burn
  review budget — stop and escalate rather than grind.
- **Never auto-apply** Critical findings, or anything outside
  `agent-review-contract.md` (e.g. `pyproject.toml` deps, security, release
  semantics, API/behavior changes without a spec). Record them as escalations.
- **Autotests must stay green** every iteration — a second, deterministic critic
  alongside CodeRabbit.
- **Read the generated code.** The human reviews the final diff; the loop is
  assistive, not autonomous. It never commits on your behalf beyond your own
  fixes, and never pushes or merges.
- **Budget:** each iteration hits the CodeRabbit API. Use `--light` for cheaper
  passes; keep diffs small.

## Running it

```
scripts/rabbit_loop.sh                    # review local changes vs origin/main + autotests
scripts/rabbit_loop.sh --base origin/main # explicit base (default)
scripts/rabbit_loop.sh --light            # cheaper CodeRabbit pass
scripts/rabbit_loop.sh --no-tests         # findings only (skip autotests)
```

**Base ref matters.** The default base is `origin/main`, not local `main`. A
stale local `main` makes CodeRabbit review *every* change merged since it — work
you never touched — producing a huge, slow, misleading review. The script warns
when local `main` lags `origin/main`; keep the base fresh (`git fetch`) or pass
`--base origin/main`. Correct base ⇒ the review covers only your diff ⇒ fast.

Findings are saved to `.rabbit-loop/findings.txt`, test output to
`.rabbit-loop/autotests.log` (both git-ignored). Maintain the human-readable
audit trail in `.rabbit-loop/state.md`:

```
## Iteration N — <date> — <branch> @ <sha>
- CodeRabbit: <count> findings
  - [High] <file:line> <summary> → FIXED (<sha>)
  - [Critical] <file:line> <summary> → ESCALATED (reason)
- Autotests: PASS/FAIL
- Verdict: ITERATE / CONVERGED
```

## When NOT to loop

- Product/architecture decisions — those are a product-owner pass, not a review
  loop (see `gittan-product-owner`).
- Changes CodeRabbit cannot judge locally (release cadence, external effects).
- Anything the review contract marks "escalate" — surface it, don't grind.
