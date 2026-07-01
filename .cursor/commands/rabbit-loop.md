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
- Ship gate: after converging, push + open/update the PR. Auto-merge **only** when
  `scripts/rabbit_loop.sh --classify-merge` prints `MERGE_CLASS: SAFE` (docs /
  skills / rules only); otherwise post a manual-test checklist and pause for the
  maintainer.
- Base defaults to `origin/main`; keep it fresh (`git fetch`).

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
