---
name: rabbit-loop
description: Run a CodeRabbit "kanin" loop-engineering pass on the current branch — generate → coderabbit review --agent (independent critic) → fix within the review contract → autotests → repeat until CodeRabbit is clean and tests are green, then hand back to the human. Use when iterating on a diff against CodeRabbit review, "run the kanin loop", "loop on the review", or converging a task branch before PR.
---

# rabbit-loop

Thin wrapper. Read and follow the canonical workflow:
**`docs/skills/rabbit-loop.md`**.

Loop-engineering pass (Addy Osmani): design a loop, don't hand-prompt. The
**independent critic** is CodeRabbit via `scripts/rabbit_loop.sh` (which also
runs autotests); you are the **generator**. Converge-then-pause — the loop never
commits beyond your own fixes, never pushes or merges.

Bounds and stopping:
- Fix only **within** `docs/decisions/agent-review-contract.md` (severity →
  allowed action; ≤5 tracked files for medium; escalate Critical / out-of-scope).
- **Stop** when `scripts/rabbit_loop.sh` prints `RABBIT_LOOP: CONVERGED`, at the
  **iteration cap (default 3)**, or when only escalations remain.
- **Ship gate:** after converging, push + open/update the PR. Auto-merge **only**
  when `scripts/rabbit_loop.sh --classify-merge` prints `MERGE_CLASS: SAFE`
  (docs / skills / rules only). Otherwise generate a concrete manual-test
  checklist with `scripts/rabbit_loop.sh --manual-test-plan` (fill each step with
  a real command + judgeable expected outcome), post it, and pause for the
  maintainer — never auto-merge shipping code, tests, config, or governance.
- Keep an audit trail in `.rabbit-loop/state.md` (git-ignored).

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
