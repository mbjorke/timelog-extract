# Timely vs Gittan — same-day event ledger benchmark

Status: active workflow (partner prep / calibration)

## Purpose

Produce a **classified comparison** of what two trackers observed on the **same closed calendar day** — for partner conversations, product calibration, or Memory.app overlap analysis.

**Do not** lead with total hours. Hours differ for session rules, dedup, and coverage; the ledger explains *why*.

**Privacy:** Keep raw ledgers, exact hour totals, and outreach drafts in local `private/`. This runbook describes the **method** only.

## When to use

- Before contacting Timely (or any automatic/memory tracker) as a design partner.
- After a Memory.app or AI-tool collector change — validate attribution lift.
- When you suspect “missed billable hours” vs “healthier noise filtering.”

## Preconditions

- **Closed day** — pick a day that is fully in the past (not today) in **one timezone** (your local wall-clock day, e.g. `Europe/Stockholm`). Use the same calendar day in Timely's UI/export and in Gittan's `--from` / `--to` so midnight boundaries do not drift.
- **Both tools ran** that day with Memory/automatic capture enabled (Timely) and normal Gittan collectors available (macOS).
- Gittan project config reflects your real customers/projects (`--projects-config` if not default).
- You accept that Timely and Gittan **measure different layers** (Memory timeline atoms vs local structured logs).

## Step 1 — Export Gittan ledger

From repo root (adjust dates and config):

```bash
# Local calendar day — must match Timely account/day view (same timezone).
DAY=2026-06-15
TZ=Europe/Stockholm gittan report --from "$DAY" --to "$DAY" \
  --format json \
  --json-file "private/benchmarks/gittan-${DAY}.json" \
  --source-summary
```

Optional: include evidence volume for dedup context:

```bash
gittan report --from "$DAY" --to "$DAY" --format json --evidence-volume
```

**Extract events** from the truth payload: each session under `days[].sessions[].events[]` has `source`, `timestamp`, `detail`, `project`. Today there is no `observation_id` in JSON — compute offline with the canonical helper (do not hand-roll concatenation):

```python
from core.evidence_record import compute_evidence_fingerprint

# observed_at: event["timestamp"] (datetime or ISO string)
fp = compute_evidence_fingerprint(event["source"], event["timestamp"], event["detail"])
```

Contract: SHA-256 over UTF-8 `source \x1f observed_at \x1f detail`, where `observed_at` is normalized to UTC ISO-8601 (`Z` → `+00:00`); return first 16 hex chars. Project is **excluded** — see `core/evidence_record.py`.

Store a flat table in `private/benchmarks/gittan-${DAY}-events.tsv` with columns:

`timestamp_utc | source | project | detail | fingerprint`

## Step 2 — Export Timely ledger (manual)

Timely's public API centers on **Hours** (approved time entries) and **entry_ids** (Memory timeline atoms linked to hours). There is no public `event_id` field.

For a fair **evidence-layer** comparison:

1. In Timely UI, open the same **DAY** timeline / memories view.
2. Export or copy **memory entries** (apps, titles, URLs, duration) — use Timely's export if available, or structured notes.
3. Optionally export **approved hours** for the same day via API (`GET /1.1/{account_id}/hours` filtered by day) — note these are **downstream** of capture, not raw parity with Gittan events.

Store as `private/benchmarks/timely-${DAY}-memories.tsv` (schema you control; keep in private).

**Do not commit** Timely exports or screenshots to the repo.

## Step 3 — Normalize both sides

Map each row to a common **comparison key** where possible:

| Key type | Gittan | Timely (typical) |
| --- | --- | --- |
| Time bucket | UTC timestamp (floor to 1–5 min) | Memory entry start |
| App/tool | `source` (Cursor, Claude Code, …) | App name / process |
| Context | `detail` (session title, path, URL redacted) | Window title + URL |
| Project | `project` | Timely project / AI suggestion |

Accept that many rows will **not** join 1:1 — classification is the point.

## Step 4 — Classify differences

For each bucket (or the day total narrative in private notes), assign primary tags:

| Tag | Meaning | Example |
| --- | --- | --- |
| **missed_evidence** | In Gittan, absent in Timely | Claude Code JSONL session with cwd/branch |
| **missed_evidence_reverse** | In Timely, absent in Gittan | Passive app time Gittan filters as noise |
| **duplicate_overlap** | Both saw same work; double-count risk | GitHub page in Chrome + GitHub API |
| **session_policy** | Same events, different hours | 15 min gap merge vs Timely segment rules |
| **source_coverage** | One tool has a collector the other lacks | Zed chat local DB vs no Timely source yet |
| **noise_filter** | Gittan excluded; Timely included (or vice versa) | Extension-host heartbeat vs Memory title |
| **attribution** | Same evidence, different project | AI suggestion vs `match_terms` |

**Scoring rule:** prefer **event counts and tagged examples** over a single hours delta.

## Step 5 — Write the one-page summary (private)

Template for `private/benchmarks/summary-${DAY}.md`:

```markdown
# Ledger benchmark — YYYY-MM-DD

## Setup
- Gittan: version, config path, command used
- Timely: Memory on/off, account type (trial/paid)

## Headline (not hours-first)
- Gittan unique observations: N (by fingerprint)
- Timely memory entries: N
- Tagged: missed_evidence A, missed_evidence_reverse B, overlap C, …

## 3 strongest Gittan-only examples
1. …
2. …
3. …

## 3 strongest Timely-only examples
1. …
2. …
3. …

## Honest gaps (for partner call)
- macOS-only collectors
- Windows / ChatGPT desktop (Timely roadmap)
- Maintenance: which sources are Tier A in CI

## Partner takeaway (one sentence)
…
```

This summary is what you bring to a CEO/engineering conversation — not a claim of parity.

## Step 6 — Maintenance narrative (if asked)

Engineering buyers will ask how collectors stay alive. Point to public artifacts:

- `gittan doctor` — source status and disable reasons
- `tests/test_*` fixtures per collector
- `docs/sources/sources-and-flags.md` — consent and roles
- Tier model (core dev/AI vs optional) — expand in private governance notes if needed

## Related docs

- [`timely-api-marketplace-benchmark.md`](../ideas/timely-api-marketplace-benchmark.md) — API patterns, identity model §7
- [`partner-briefs/timely.md`](../ideas/partner-briefs/timely.md) — offer shapes and 90-day plan
- [`screen-time-gap-analysis.md`](screen-time-gap-analysis.md) — Gittan vs Screen Time (different question)
- [`timelog-truth-check.md`](timelog-truth-check.md) — determinism replay (CI evidence)

## Out of scope

- Automated Timely API importer in Gittan (future integration slice).
- Committing benchmark numbers or customer-identifying details to git.
- Proving either tool is “more correct” on total hours alone.
