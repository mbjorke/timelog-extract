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

**Critic fallback (CodeRabbit rate-limited / down):** use `/gittan-review` as the
independent critic instead (Claude Code's own model, no third-party rate limit),
or `/code-review ultra` for high-risk PRs. Run it as a fresh adversarial pass, not
self-grading. Shared lens for every reviewer: `docs/reviews/review-lens-guidelines.md`.

**Step 0a (session title):** if preflight / `--chat-summary` suggests
``#N · topic``, rename **this** Claude session with:

```text
/rename #N · topic
```

(Best-effort; never block the loop. Full matrix:
`docs/skills/session-title-adapters.md`.)

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
- **Merge gate (even for SAFE):** immediately before `gh pr merge`, run
  `scripts/rabbit_loop.sh --merge-gate [--pr N]`. `BLOCKED` (unresolved review
  threads, bot or human) → do **not** merge; reply + resolve every thread, then
  re-run until `CLEAR`.
- Keep an audit trail in `.rabbit-loop/state.md` (git-ignored).

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
