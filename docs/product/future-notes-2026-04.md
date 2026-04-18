# Product notes — April 2026 (ideas, not commitments)

Working notes captured so they do not live only in chat. **Not a roadmap promise** — prioritize via normal release planning.

## Time context (author)

- Same calendar day: **~2 h** available total (short slot now + longer slot later). Favors **one** shippable slice over parallel epics.

## AI-assisted help in the CLI (when / how big)

**Distinction that matters**

- **Command-aware helper** — suggests next `gittan …` steps, explains `doctor` output, links to docs. Stays aligned with the tool; low data exfil risk if it does not send raw timelines off-device.
- **Free-form chat over pasted data** — flexible, but **privacy and correctness** burden jumps (users paste more than they intend; cloud LLMs add policy/consent surface).

**Size**

- **Smaller:** contextual hints, fixed “explain this JSON export” flows, no automatic shell execution.
- **Larger:** natural language → **executed** commands or uploads of raw activity payloads — needs explicit trust, guardrails, and maintenance.

**When it is appropriate**

- When there is a **clear user job** (“why is my report empty?”, “what flag for Screen Time?”) and a **bounded** integration — not when “AGI” arrives. Early adopters (even **n = 1** working end-to-end) are enough to validate *workflow fit*; broader patterns need more users.

## “Bottom prompt” / persistent input area

Treat as **UI chrome**, not intelligence. Add when:

- it solves a **specific** interaction cost (e.g. always-visible next command, sponsor/support line, or single-line “ask about this error”), and
- you are willing to **maintain** it across terminal sizes and themes.

Defer if it is only “feels modern” without a job-to-be-done.

## CLI design regression / “design system” tests

**Feasible directions**

- Keep **token discipline** in `outputs/terminal_theme.py` + `docs/product/terminal-style-guide.md` (already the contract).
- Add later: **golden text snapshots** for a **few** stable commands (e.g. `ux-heroes`, a tiny doctor fixture) — high maintenance if copy changes often; choose surfaces deliberately.

## Accuracy work and Screen Time gap

**Status**

- **Gap analysis is implemented:** `core/calibration/screen_time_gap.py`, tests under `tests/test_screen_time_gap_analysis.py`, entrypoint `python3 scripts/run_screen_time_gap_analysis.py` (wrapper → `scripts/calibration/run_screen_time_gap_analysis.py`).
- What was missing for “release completeness” was mainly **discoverability** — users and release notes should point at a single runbook.

**Staging ladder (incremental)**

1. **Done in this batch:** runbook + links from accuracy material and README map (**documentation-only**, tests stay green).
2. **Later:** optional `gittan` subcommand or `report` flag that runs the same analysis and writes under a documented path (more code + tests).

## Single improvement chosen for “green today”

**Surface Screen Time vs estimates reconciliation** without new CLI surface:

- Add **`docs/runbooks/screen-time-gap-analysis.md`** (how + outputs).
- Link from **`docs/product/accuracy-plan.md`** and the **documentation map** in the root README.

This is the fastest path to a **releasable** documentation increment aligned with accuracy/precision goals on `feat/*` branches.

## Richer time semantics (Jira-style “accuracy”, provability, analytics)

**Observation**

- Systems such as **Jira** (worklogs and related APIs) often carry **more than a single naive timestamp** — e.g. when a worklog entry was logged, start/end of work, resolution time, or other fields that imply **ordering and confidence** beyond “everything happened at the same second.”
- Local traces in Gittan are often **normalized to coarse or identical instants** (same second, batch imports), which weakens **story order**, **auditability**, and **cross-tool correlation**.

**Possible directions (explore before building)**

- **Preserve upstream precision** where the source provides it (sub-second or explicit sequence), and **store provenance** (“this time came from Jira field X, not inferred”).
- **Expose explicit uncertainty** when we must collapse times (documented heuristic, not silent equality).
- **Export shapes** that work in **Splunk / log analytics** — stable `_time` or equivalent, tie-breakers for simultaneous events, optional correlation IDs so stacks and IDE events sort believably.
- **Trust / evidence** — for “invoice-grade” or “dispute-grade” narratives, richer metadata may matter as much as raw hours.

**Open questions**

- Which Jira (or other) fields are authoritative for *work performed* vs *time recorded*?
- What is the minimum schema extension in exports (JSON/CSV) without breaking existing consumers?

## Integration layer: open source vs commercial

**Tension**

- The **core** local-first engine benefits from **GPL and community review**.
- **Connectors** to commercial systems (issue trackers, billing, enterprise SSO, SaaS without usable free tiers) can imply **API keys, partner programs, compliance review**, and **ongoing breakage** when vendors change APIs — maintenance cost scales with surface area.

**Options to consider (not a decision)**

- **OSS core + documented integration hooks** (stable export formats, webhooks, “bring your own script”) so proprietary or paid connectors can live **outside** the main repo under a different license or vendor agreement.
- **Commercial or closed “integration pack”** for orgs that need supported connectors and SLAs, while keeping the **local extraction and reporting story** open.
- **Criteria:** where free tiers exist and APIs are stable, OSS connectors may still make sense; where they do not, **splitting the layer** avoids GPL obligations on third-party SDKs that are not redistributable or that require contractual terms.

**Next step when this becomes active**

- Write a short **decision memo** under `docs/decisions/` (audience: you + future contributors): scope of “core” vs “integrations”, license intent, and what must remain reproducible from source for trust.
