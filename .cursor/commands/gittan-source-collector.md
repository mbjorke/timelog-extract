---
description: Gittan source-collector skill — add/change a data source against the collector + evidence contracts
---

# `/gittan-source-collector` (gittan / sources)

Thin wrapper. The canonical workflow lives in
**`docs/skills/gittan-source-collector.md`** — read and follow it.

**Use when:** adding or changing anything under `collectors/`, or debugging why a
source returns no events.

**Mechanics:**
- Read `docs/specs/source-collector-contract.md` and
  `docs/specs/source-evidence-policy.md`; pick the **source role** first.
- A collector is evidence, not truth — declare role + retention before code.
- Add a `## Behavior Contract` before implementing; tests must use fixtures, not
  live user data.

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
