# Case Study: Timelog Extract

## One-line Summary

Timelog Extract turns fragmented local work signals into a clear, auditable time report and optional invoice-ready output, helping solo consultants and small teams bill faster with more confidence.

## The Problem

Knowledge work now happens across many tools in parallel:

- AI coding sessions
- editor activity and checkpoints
- terminal commands
- browser and chat interactions
- handwritten or markdown worklogs

At invoicing time, this creates three recurring issues:

1. **Lost billable time**  
   Small sessions are forgotten because they are spread across tools.
2. **Weak evidence for clients**  
   Manual summaries are often too vague to justify hours.
3. **High admin overhead**  
   Reconstructing a week or month of work manually is slow and mentally expensive.

## Who It Helps

- Independent consultants and freelancers billing by hour or project
- Small agencies working across multiple clients
- Product or engineering leads who need transparent effort summaries

## Why Existing Workflow Breaks

Typical workflows rely on either:

- manually maintained worklogs, or
- a single-source tracker that misses real activity.

Modern development includes AI-assisted workflows and multi-tool context switching, so single-source reporting misses meaningful work. Timelog Extract is built for this new reality.

## Solution Overview

Timelog Extract is a local-first Python/CLI tool (with GUI extension scaffolding) that:

1. Collects events from configured local and optional external sources.
2. Classifies activity into project/customer buckets using matching rules.
3. Builds session-level summaries and source breakdowns.
4. Outputs reports for human review and downstream automation.

## What It Produces

- Terminal summary report (`--source-summary`)
- Rule-based executive narrative (`--narrative`, no LLM required)
- Versioned JSON truth payload (`--format json`, optional `--json-file`)
- Single-file HTML timeline (`--report-html`)
- Optional invoice PDF output (`--invoice-pdf`)

## Key Product Decisions

- **Local-first by default**: core flow is designed to run without cloud upload.
- **Transparent output**: structured JSON payload enables auditability and integrations.
- **Pragmatic source coverage**: supports modern AI/dev workflows, not only classic timers.
- **Incremental trust**: narrative output is deterministic and rule-based.

## What Changed Recently (Current Momentum)

Recent updates strengthened the core value proposition:

- Added versioned JSON truth payload and HTML timeline export.
- Added deterministic executive narrative for stakeholder-friendly summaries.
- Added optional GitHub activity source for broader signal coverage.
- Improved English output across terminal and PDF labels.
- Added worklog format flexibility (`TIMELOG.md` and gtimelog-style text).

Together, these changes moved the project from "raw extraction utility" to "client-ready reporting pipeline."

## Business Outcome

Timelog Extract reduces the gap between "work done" and "work billed" by producing:

- faster end-of-day and end-of-week reporting,
- clearer client-facing evidence,
- lower risk of under-billing,
- reusable structured data for future automation.

## Why This Matters Now

As AI-assisted development accelerates delivery, more work happens in rapid, fragmented micro-sessions. Teams need reporting that matches how they actually work, not how legacy tracking tools assume they work.

Timelog Extract addresses this shift directly by turning fragmented activity into coherent, invoice-adjacent outputs.

## How to Try It

Quick run for today:

`python3 timelog_extract.py --today --source-summary --narrative --invoice-pdf`

Engine-boundary run (same contract used by the extension):

`python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json`

JSON + HTML timeline export:

`python3 timelog_extract.py --from 2026-04-01 --to 2026-04-30 --format json --json-file out/truth.json --report-html out/report.html`

## Next Step

Publish this case study in the repository and reuse it as the source narrative for:

- a longer blog post (build story + lessons),
- a LinkedIn article/post (business value + call to action),
- product page copy (problem, proof, and outcomes).
