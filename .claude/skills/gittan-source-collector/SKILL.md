---
name: gittan-source-collector
description: Add or change a Gittan data source/collector against the collector + evidence contracts (source role, consent, collector_status, doctor, fixture tests, retention). Use when editing anything under collectors/ or debugging why a source returns no events.
---

# gittan-source-collector

Thin wrapper. Read and follow the canonical workflow:
**`docs/skills/gittan-source-collector.md`**.

Pick the **source role** from `docs/specs/source-evidence-policy.md` first (a
collector is evidence, not truth). Honor `docs/specs/source-collector-contract.md`:
enablement modes, date-window, `collector_status` states, a doctor row, privacy,
and tests on fixtures (never live user data). Add a `## Behavior Contract` before
implementing.

Policy (branches, safety, tests, PR language): **`AGENTS.md`**.
