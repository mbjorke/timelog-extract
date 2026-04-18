# Decision: Agent review contract (CodeRabbit signal → human or Cursor execution)

Status: Draft (process template)  
Date: 2026-04-18  
Owner: Maintainer + active agents

## Why

Automated review (often **CodeRabbit** in this repo) produces **findings**; **execution** (fixes) may be done by a **human** or by a **Cursor agent** (or another coding agent). Those are different systems: there is **no** guaranteed machine-to-machine contract between “review bot” and “IDE agent” unless we **define one in the repo** and follow it manually or via vendor features.

This document sketches a **pre-agreed contract** so that:

- **High-severity** items get **explicit** handling expectations.
- **Executors** know what they may change **without** a new product decision.
- **Review threads** stay the source of truth for *what* was wrong; this doc defines *how* we respond by severity.

## Roles

| Role | Typical tool | Responsibility |
|------|----------------|----------------|
| **Reviewer / signal** | CodeRabbit (GitHub app or `coderabbit` CLI) | Flag issues, severity, concrete suggestions. Does not replace maintainer judgment. |
| **Executor** | Human, or Cursor Cloud / IDE agent | Implement fixes **within the contract**; push commits; reply in thread with SHA. |
| **Gate** | Maintainer | Approves anything outside the contract or that touches security, licensing, or release semantics. |

## Severity → allowed response (contract)

Adjust labels to match your tracker; default mapping:

| Severity | Meaning (examples) | Executor **may** do without extra approval | **Always** escalate |
|----------|---------------------|---------------------------------------------|----------------------|
| **Critical** | Secret exposure, auth bypass, data loss risk | **Nothing automatic.** Open a focused fix or revert; page maintainer if needed. | Dependency with legal review, production creds |
| **High** | CI broken, test wrong, clear bug with bounded patch | Fix **only** the cited files/lines; add/adjust tests proving the fix; one logical commit per batch. | API/behavior change affecting users without spec |
| **Medium** | Style, maintainability, missing edge-case test | Same as high if change is **≤ N files** (set N in team practice, e.g. 3) and tests pass. | Refactors that broaden scope |
| **Low** | Nit, doc typo, optional cleanup | Batch in a single “chore” commit if desired; or defer. | — |

**Repo-specific add-ons** (fill in as needed):

- Allowed to touch: `tests/`, `docs/runbooks/`, …
- Forbidden without PR description: `pyproject.toml` deps, license headers, `timelog_projects.json` schema.

## Hand-off protocol (practical)

1. **Reviewer** leaves findings on the PR (or CLI output before push).
2. **Executor** addresses **high** first (or critical first), within the table above.
3. Reply in thread: `Addressed in <short-sha>: <one line>` then resolve when CI is green.
4. If a finding is **out of contract** (e.g. “large refactor”), reply: **Deferred: reason** and link an issue or decision doc.

This is the closest we get to a “pre-agreed contract” until vendors offer a **single** negotiated channel between review bots and IDE agents.

## CodeRabbit: cloud features that relate to “rabbit asks, agent fixes”

Product names and availability change — use **[CodeRabbit documentation](https://docs.coderabbit.ai/)** and **[changelog](https://docs.coderabbit.ai/changelog)** as source of truth. As of common 2025–2026 messaging, items in this family include:

- **Autofix / automated fixes** — applies certain fixes on the PR branch (scope and safety rules are product-defined; not the same as Cursor).
- **Fix-all / batched remediation** — aggregates findings so one can drive a **single** agent session or pass (see also their blog on *fixing issues with AI agents*).
- **Pipeline remediation** — CI failure diagnosis/fix flows for common CI systems.
- **CodeRabbit Skills** — integrations so **Skills-compatible agents** can trigger reviews from natural language (still **not** a bilateral Cursor ↔ CodeRabbit negotiation in one thread).
- **CLI** (`coderabbit review`) — local review without consuming GitHub **hourly** review quota the same way; see `AGENTS.md`.

**Interpretation:** CodeRabbit has been **shipping** cloud-side automation that **narrows the gap** between “findings” and “applied fixes,” but **your** contract (this doc + `AGENTS.md`) still defines **what** a Cursor agent may do **in this repository**.

## Relation to Cursor

- **Cursor agents** do not receive a formal API callback from CodeRabbit when severity = high.
- Practical pattern: **export** findings (PR tab, or paste CLI summary) → **prompt Cursor** with: “Fix only HIGH items in scope X per `docs/decisions/agent-review-contract.md`.”
- If GitHub/Cursor later adds **@mentions** or **agent triggers** on PRs, revisit this doc and add a subsection.

## Links

- Review cadence and rate limits: [`AGENTS.md`](../../AGENTS.md) → *Review Cadence (CodeRabbit)*.
- Task handover prompt: [`docs/contributing/agent-task-handover-prompt.md`](../contributing/agent-task-handover-prompt.md).
