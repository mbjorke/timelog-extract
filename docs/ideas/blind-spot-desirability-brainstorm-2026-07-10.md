# Brainstorm record — blind-spot + desirability passes (2026-07-10)

**Status:** Idea record, not a backlog spec. This is the distilled output of two
exploratory brainstorm passes, kept for provenance. The actionable insights have
been **folded into existing artifacts** (see "Where each insight landed"); nothing
here is a standalone task-prompt or a competing `now` list. The canonical ordered
backlog remains `docs/task-prompts/backlog-priority-2026-07-08-task.md` (GH-317).

**Technique:** map-vs-territory "blind spot pass" (Thariq Shihipar, *A Field Guide
to Fable: Finding Your Unknowns*) — surface *unknown unknowns*, the gaps between
the **map** (our docs/policies/vision) and the **territory** (what the code and the
product actually do). One pass read the **code** (correctness/risk unknowns); the
second read the **product** (desirability/adoption unknowns).

## Why this is an idea record and not two specs

The two passes were run as one brainstorm, and each produced its own
`now`/`next`/`later` ordering. Left as task-prompts they created **three competing
`now` lists** alongside the two-day-old GH-317 whole-backlog pass — planning on top
of planning, the "admin ritual" product soul #3 warns against. So the passes were
demoted to this single record and their genuine insights routed into what already
exists.

## Insight → where it landed

| Insight | Source pass | Folded into |
| ------- | ----------- | ----------- |
| `gittan --today` dead-ends (`No such option`); CI smoke masked by `\|\| true` | desirability | `CLAUDE.md` smoke section (fixed) + GH-123 `agent-inline-cli-ux-validation` (motivating regression + acceptance case) |
| First run leads with caveats, not value | desirability | `docs/product/terminal-style-guide.md` — "Value before caveats" structural rule |
| Collectors swallow errors → silently missing billable hours | blind-spot | `docs/sources/sources-and-flags.md` — collector_status "partial failure must be visible" contract |
| First run must deliver value before it asks for trust-review | desirability (meta) | proposed one-line vision sharpening (`docs/product/gittan-vision.md`) — pending maintainer approval |
| Config cliff keeps classification specialist-only | desirability | already tracked/shipped: GH-197 `project-config-onboarding-guidance` (built); north star `docs/sources/ai-assisted-config.md` |
| Repo-centric first run looks "empty" | desirability | already planned: `docs/product/worklog-first-strategy-plan.md` |

## Insights parked (not promoted)

From the blind-spot pass, correctness items that are **not** `now` against GH-317's
invoice-trust filter (#263/#284 are the live core) — kept here as parking, promote
only if evidence warrants:

- **Session cross-project attribution** — verify `compute_sessions` /
  `aggregate_report` never merge two projects' events within the gap window before
  assuming a bug; spike-first.
- **Consent/retention coverage** — only ~4 of ~24 collectors declare a role; an
  audit would convert the unknown to a known list (may be fine for passive-context
  sources).
- **Test backfill** for `git_commits`, `ai_logs`, `cursor_log_scan`, `vscode_fork`.
- **500-line gate is gamed to 499** — measure complexity, not raw lines (later).
- **`TRUTH_PAYLOAD_VERSION` frozen at "1"** — write a versioning/migration policy
  before the first forced bump (later).

## The meta-unknown neither pass could close

A blind-spot pass reads code; a desirability pass reads users — but this one read
only the vision and a single first-run, **not real users**. The largest
desirability unknowns (would the aspirational audience adopt? what do they value
first?) need observed behavior. The honest next move is to **watch 3–5 real
first-runs** and let that re-order the backlog — the same "map is not the
territory" discipline applied to desirability.
