---
description: Kanin-loop — CodeRabbit + autotests convergence loop (loop-engineering) with a class-based ship gate
---

# `/rabbit-loop` (CodeRabbit loop-engineering)

Thin wrapper. The canonical, editor-agnostic workflow lives in
**`docs/skills/rabbit-loop.md`** — read and follow it.

**Use when:** converging a `task/*` branch against CodeRabbit review before PR, or
"run the kanin loop / loop on the review".

**Mechanics:**
- Loop: implement → `scripts/rabbit_loop.sh` (CodeRabbit `--agent` + autotests) →
  fix **within** `docs/decisions/agent-review-contract.md` → repeat until
  `RABBIT_LOOP: CONVERGED`. Iteration cap 3; escalate Critical / out-of-scope.
- Ship gate (judgment, not file type): after converging, push + open/update the PR,
  then `scripts/rabbit_loop.sh --classify-merge`. `SAFE` → **auto-merge** (squash)
  when CONVERGED. `NEEDS_HUMAN` (report/invoice engine, `collectors/`, `outputs/`,
  deps, CI, governance) → generate a checklist with
  `scripts/rabbit_loop.sh --manual-test-plan`, post it, and pause for the maintainer.
- Base defaults to `origin/main`; keep it fresh (`git fetch`).

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
