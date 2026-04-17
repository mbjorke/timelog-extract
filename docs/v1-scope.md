# V1 Scope Decision

## Product Shape

- Delivery target: Cursor Marketplace plugin (GUI-first), backed by local Python engine.
- Processing mode: local-only for v1 (no cloud upload path to Gittan-operated services; no **cloud-agent platform** connectors in v1 — see **Sources Deferred**).

## Supported OS (v1)

- Primary support: macOS.
- Linux/Windows: graceful unsupported-source behavior only, no parity promise in v1.

## Sources Included in v1

- AI coding assistant CLI logs
- AI desktop assistant sessions
- Tracked AI chat URLs (`tracked_urls`)
- AI terminal/chat CLI session logs
- Cursor logs + Cursor checkpoints
- Codex IDE index
- Project worklog (`TIMELOG.md`)

## Sources Deferred

- **Cloud-agent platforms** (optional connectors that pull job-level metadata—runs, cost, links to outputs—from third-party agent APIs using the user’s credentials): **not in v1**; treated as **post-v1 / backlog**. Root `VISION.md` and `docs/gittan-vision.md` describe this direction so marketing stays honest; **shipped v1** remains the **local trace** sources listed above until explicitly added here.
- Apple Mail and Screen Time as default-enabled sources are deferred behind explicit opt-in.
- Full Briox invoice push flow deferred to v1.1+ (keep read/test integration outside core plugin path).
- **ActivityWatch** (optional local activity aggregator): **not in v1**; rationale and integration sketch in **`docs/activitywatch-integration.md`**.

## v1 UX Commitments

- Setup wizard
- Data-source consent screen
- Source toggles
- Run report action
- Results summary view
- Export/open PDF actions

