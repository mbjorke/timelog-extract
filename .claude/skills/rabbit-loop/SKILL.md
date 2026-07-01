---
name: rabbit-loop
description: Run a CodeRabbit "kanin" loop-engineering pass on the current branch — generate → coderabbit review --agent (independent critic) → fix within the review contract → autotests → repeat until CodeRabbit is clean and tests are green, then hand back to the human. Use when iterating on a diff against CodeRabbit review, "run the kanin loop", "loop on the review", or converging a task branch before PR.
---

# rabbit-loop

Thin wrapper. Read and follow the canonical workflow:
**`docs/skills/rabbit-loop.md`**.

Loop-engineering pass (Addy Osmani): design a loop, don't hand-prompt. The
**independent critic** is CodeRabbit via `scripts/rabbit_loop.sh` (which also
runs autotests); you are the **generator**. After converging, the loop pushes +
opens a PR and auto-merges the SAFE class; it pauses only for human-judgment
changes (see Ship gate).

Bounds and stopping:
- Fix only **within** `docs/decisions/agent-review-contract.md` (severity →
  allowed action; ≤5 tracked files for medium; escalate Critical / out-of-scope).
- **Stop** when `scripts/rabbit_loop.sh` prints `RABBIT_LOOP: CONVERGED`, at the
  **iteration cap (default 3)**, or when only escalations remain.
- **Ship gate (judgment, not file type):** after converging, push + open/update
  the PR, then `scripts/rabbit_loop.sh --classify-merge`. `MERGE_CLASS: SAFE` →
  **auto-merge** (squash) when CONVERGED. `NEEDS_HUMAN` (touches the report/invoice
  engine, `collectors/`, `outputs/`, packaging (`pyproject.toml`), CI, or governance) → generate a concrete
  checklist with `scripts/rabbit_loop.sh --manual-test-plan` (real command +
  judgeable expected outcome per step), post it, and pause. Never auto-merge unless
  CONVERGED.
- Keep an audit trail in `.rabbit-loop/state.md` (git-ignored).

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
