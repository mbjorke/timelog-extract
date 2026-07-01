# rabbit-loop — CodeRabbit loop-engineering workflow

Canonical, **editor-agnostic** workflow for the kanin-loop. A **loop-engineering**
pass (Addy Osmani, https://addyosmani.com/blog/loop-engineering/): instead of
hand-prompting turn-by-turn, run a **loop** where a generator produces work, an
**independent critic** grades it against a verifiable condition, the generator
fixes within bounds, and the loop repeats until a **stopping condition** holds —
with state on disk and the human staying engaged.

The critic is **CodeRabbit** ("kanin"), run locally via its CLI, plus autotests.
Both are different systems from the generator, so they do not self-grade its work.

**Any coding agent can run this** — the engine is `scripts/rabbit_loop.sh` + this
doc, not any one editor. See *Invoking it per agent* below.

Policy (branches, PR language, safety, tests): **`AGENTS.md`**.
Fix bounds by severity: **`docs/decisions/agent-review-contract.md`**.

## Roles (generator vs critic)

| Role | Who | Does |
|------|-----|------|
| Generator | **your coding agent** (Claude Code, Cursor, Zed, Codex, Conductor, Antigravity, …) | implements the task, commits, applies in-contract fixes |
| Critic 1 | **CodeRabbit CLI** | independent review of the local diff → structured findings |
| Critic 2 | **autotests** | `scripts/run_autotests.sh` (500-line gate + unit tests) |
| Gate | **maintainer (human)** | final review; auto-merge only for the safe class (Ship stage) |

## The loop (converge-then-pause)

```text
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
- **Read the generated code.** The loop is assistive. After it converges it may
  push and open a PR, but it **auto-merges only the safe class** (see Ship stage);
  anything touching shipping code, tests, config, or governance pauses for you.
- **Budget:** each iteration hits the CodeRabbit API. Use `--light` for cheaper
  passes; keep diffs small.

## Running it

```bash
scripts/rabbit_loop.sh                    # review local changes vs origin/main + autotests
scripts/rabbit_loop.sh --base origin/main # explicit base (default)
scripts/rabbit_loop.sh --light            # cheaper CodeRabbit pass
scripts/rabbit_loop.sh --no-tests         # findings only (skip autotests)
scripts/rabbit_loop.sh --classify-merge   # ship gate: MERGE_CLASS SAFE | NEEDS_HUMAN
```

### Invoking it per agent

The loop is the **script + this doc**; the only per-agent difference is how you
launch it. In every case the agent then reads this doc and drives the loop.

| Agent | How to start |
|-------|--------------|
| **Claude Code** | `/rabbit-loop` (skill: `.claude/skills/rabbit-loop/SKILL.md`) |
| **Cursor** | `/rabbit-loop` (command: `.cursor/commands/rabbit-loop.md`; rule auto-attaches on a task branch) |
| **Zed / Codex / Conductor / Antigravity** | run `scripts/rabbit_loop.sh` and follow this doc — these agents read `AGENTS.md`, which points here (§ *Review Cadence*) |

Any agent that can run a shell command and edit files can execute the full loop;
no editor-specific integration is required beyond the launch surface above.

**Base ref matters.** The default base is `origin/main`, not local `main`. A
stale local `main` makes CodeRabbit review *every* change merged since it — work
you never touched — producing a huge, slow, misleading review. The script warns
when local `main` lags `origin/main`; keep the base fresh (`git fetch`) or pass
`--base origin/main`. Correct base ⇒ the review covers only your diff ⇒ fast.

Findings are saved to `.rabbit-loop/findings.txt`, test output to
`.rabbit-loop/autotests.log` (both git-ignored). Maintain the human-readable
audit trail in `.rabbit-loop/state.md`:

```text
## Iteration N — <date> — <branch> @ <sha>
- CodeRabbit: <count> findings
  - [High] <file:line> <summary> → FIXED (<sha>)
  - [Critical] <file:line> <summary> → ESCALATED (reason)
- Autotests: PASS/FAIL
- Verdict: ITERATE / CONVERGED
```

## Ship stage (converge → push → PR → gate)

Once `scripts/rabbit_loop.sh` reports `RABBIT_LOOP: CONVERGED`, the loop may ship —
but the **merge gate is by change class**, decided mechanically:

```bash
scripts/rabbit_loop.sh --classify-merge     # MERGE_CLASS: SAFE | NEEDS_HUMAN
```

1. **Push** the branch and **open or update the PR** (English title/body per `AGENTS.md`;
   include the converged CodeRabbit summary and any escalations — no private customer data).
2. **Classify** the committed diff vs `origin/main`:
   - **SAFE** — every changed path is under `docs/`, `.claude/skills/`, or `.cursor/rules/`
     (docs / skills / rules only; no shipping code, tests, config, or governance). The loop may
     **auto-merge** (squash) and report back.
   - **NEEDS_HUMAN** — any path outside that allowlist (e.g. `core/`, `collectors/`, `outputs/`,
     `scripts/`, `tests/`, `pyproject.toml`, `AGENTS.md`, `.github/`). The loop **stops**, produces a
     **manual-test checklist** (below), and **pings you**. You run the checklist and click merge.

The classifier is intentionally strict: a misclassified auto-merge is worse than an unnecessary
pause. Widen `SAFE_MERGE_PREFIXES` in `scripts/rabbit_loop.sh` only with a deliberate decision.

**Never auto-merge** — regardless of class — if CodeRabbit did not complete cleanly, tests are
not green, or any escalation is unresolved. Auto-merge requires `CONVERGED` **and** `SAFE`.

### Manual-test checklist (the NEEDS_HUMAN handoff)

A pause is only useful if you know *what* to test. The loop **must** hand you a concrete,
runnable checklist — never "please test this." Generate the scaffold, then complete it:

```bash
scripts/rabbit_loop.sh --manual-test-plan > .rabbit-loop/manual-tests.md
```

The scaffold maps each changed **area** to a verification command (collectors → `gittan-dev
doctor` + source-summary; outputs → a `gittan-dev report` render; core → autotests + a report on
a known window; CLI/scripts → `--help` + a representative run; `pyproject.toml` → build/install).
The agent then **fills every step**:

- a **concrete command** (real window, real args — not `<window>`), and
- an **expected outcome the human can judge** — a specific number, table shape, exit code, or row.
  No "looks right" / "seems fine" — if it can't be judged, it isn't a test step.

Post the completed checklist to the PR (or hand it over directly) and pause. Unknown/root files
map conservatively to a behavior check — over-prompting beats missing a regression.

## When NOT to loop

- Product/architecture decisions — those are a product-owner pass, not a review
  loop (see `gittan-product-owner`).
- Changes CodeRabbit cannot judge locally (release cadence, external effects).
- Anything the review contract marks "escalate" — surface it, don't grind.
