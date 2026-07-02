# Partner brief — Timely

**Status:** Draft hypothesis — not outreach, not a term sheet.

**Relationship (draft):** Compete on the **evidence layer** (Memory.app / AI-tool capture) *and* potentially **partner** if Timely prefers to license or co-develop developer-grade collectors instead of rebuilding every AI/IDE source in-house.

**Last updated:** 2026-07-01

---

## Why Timely is a dream partner

Timely already sells the outcome Gittan targets for consultants and agencies:

- automatic capture → allocation → human approval,
- privacy-first (no screenshots/keylogs),
- billing accuracy and admin reduction.

Their **Memory.app** work on Claude/Codex/IDE context is direct overlap with Gittan's collector engine — which means they feel the same maintenance pain (new AI tools, changing log paths, schema drift).

**Gittan brings:** CLI-first local evidence, inspectable sources, fast niche collector iteration, JSON truth payload, open-source transparency, structured logs (session title, cwd, git branch) vs OS-level window titles.

**Timely brings:** app UX, team workflows, enterprise sales, billing/capacity features Gittan should not build first.

---

## Where Gittan is stronger (hypothesis — validate with ledger benchmark)

| Dimension | Timely Memory.app (public positioning) | Gittan (local collectors) |
| --- | --- | --- |
| AI/dev capture | Window title + URL where available | Structured local logs (Claude Code JSONL, Claude Desktop session cache, Codex IDE index, Cursor, Zed, etc.) |
| Project attribution | AI prediction on timeline | `match_terms`, anchors (dir, branch, repo slug), review flow |
| Inspectability | Hosted timeline | `gittan report --format json`, source + detail per event |
| Platform | Expanding (Windows/ChatGPT desktop on roadmap per their posts) | macOS-primary v1 — **honest boundary in any conversation** |

Do **not** open with “we already have what you need.” Open with a **classified same-day ledger diff** — see the benchmark runbook.

---

## Problem we solve for them (hypothesis)

| Their pain | Gittan angle |
| --- | --- |
| AI/vibe-coding tools change faster than desktop memory can keep up | Source-specific collectors + fixtures + `gittan doctor` |
| Developer/consultant trust requires explainable evidence | Per-event source, detail, project — review before export |
| Building every IDE/CLI integration in a desktop app is expensive | Engine boundary: collectors + classification + export contract |

---

## Maintenance answer (expect this from an engineering-led buyer)

Every new source has ongoing cost: schema drift, noise filters, fixtures, platform paths. Gittan's answer is not “set and forget”:

- **Tier A sources** — core dev/AI stack; fixture tests in CI; doctor surfaces disable reasons.
- **Tier B sources** — optional/opt-in; clear degradation when paths missing.
- **Evidence contract** — `fingerprint` / future `observation_id` for stable dedup and ledger diffs.
- **Open core** — collectors and contracts visible; partner can audit or co-fund specific sources.

Details for negotiation stay in `private/`; public contract references: `docs/sources/sources-and-flags.md`, `docs/specs/local-evidence-shadow-log.md`.

---

## Offer shapes (pick one for first conversation)

1. **Design partner (lowest friction)** — Timely funds or sponsors 3–6 months of collector roadmap (Claude/Codex/Cursor/Zed/GitHub depth); Gittan ships open improvements; Timely evaluates import/API fit.
2. **Evidence export contract** — Stable JSON bundle: sessions, sources, `observation_id` (fingerprint), external links, project tags — consumed by Timely after user consent. Gittan stays local-first.
3. **Licensed engine / OEM (highest upside, hardest)** — Separate license from GPL app (requires explicit legal shape).

**Not proposing:** forced cloud timeline upload or replacing Memory.app UI on day one.

---

## 90-day proof plan (if either side says yes)

| Week | Gittan deliverable | Success signal |
| --- | --- | --- |
| 1–2 | Same-day **event ledger benchmark** (Timely vs Gittan) with classified diff | Diff report: missed evidence, overlap, session policy, noise — not total hours alone |
| 3–4 | Export contract v0 documented | Timely eng can map fields without reading all collectors |
| 5–8 | Harden 2–3 AI sources + GitHub spike spec | Fewer uncategorized dev events; reproducible fixtures |
| 9–12 | Pilot with 3–5 design-partner users | Users prefer merged story for billing review; no privacy backlash |

---

## Open questions

- Competitive boundary: Memory.app roadmap vs partner surface — can both be true?
- GPL / embedding: separate process vs API boundary?
- Data residency: no raw trace upload unless user explicitly exports?
- macOS-only v1 vs their Windows expansion — complement or gap?

---

## What stays in `private/`

Exact hour totals, CEO LinkedIn drafts, price anchors, acqui-hire tone.

---

## References

- [Timely Memory.app Claude/Codex update](https://www.timely.com/product-updates/2026-05-07-memory-app-claude-codex-tracking/)
- [`timely-api-marketplace-benchmark.md`](../timely-api-marketplace-benchmark.md) — API identity model (§7)
- [`timely-gittan-event-ledger-benchmark.md`](../../runbooks/timely-gittan-event-ledger-benchmark.md)
