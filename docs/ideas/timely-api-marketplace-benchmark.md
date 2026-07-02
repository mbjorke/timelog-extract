# Timely API + GitHub Marketplace benchmark notes

**Status:** Product / integration idea, not a commitment.

**Reviewed:** 2026-07-01 from Timely's public OpenAPI document and the public GitHub Marketplace listing.

**Scope:** Product-pattern notes only — not side-by-side hour totals, customer names, or outreach drafts (those stay in local `private/` notes).

---

## Why this matters

Timely is already listed on GitHub Marketplace as a time-tracking app for GitHub work. That makes it a useful benchmark for two separate questions:

1. **Product quality:** what Git/GitHub evidence do users expect an automatic time-reporting tool to understand?
2. **Distribution:** what shape would Gittan need before a GitHub Marketplace listing is credible?

Side-by-side testing against another tracker can show a same-day gap between Git-derived estimates. Treat that as a calibration prompt, not as proof that either product is automatically more correct. More hours can mean better recall, duplicated evidence, broader source coverage, or over-counting; fewer hours can mean missed evidence, stricter session rules, or healthier noise filtering.

---

## What Timely's marketing suggests

Timely's homepage does not lead with APIs or raw tracking mechanics. It frames the product as business automation:

- **Core promise:** “The AI time tracker to end time tracking.”
- **Three-step UX:** auto-capture → auto-allocate → one-click approve.
- **Buyer outcomes:** profitability up, utilization up, compliance up, admin down, risk down, capacity/planning confidence up.
- **Adoption argument:** manual timesheets fail because people forget, misallocate, or avoid them; automatic capture plus approval improves trust and completeness.
- **Trust stance:** “Privacy-first. Not spyware.” The page explicitly says private timelines, user-approved sharing, granular capture/visibility settings, transparency, no keystroke logging, and no screenshots.
- **Enterprise proof:** ISO/GDPR language, SSO, permissions, support, and scale.
- **Conversion assets:** free trial, demo, ROI calculator, G2/social proof, integrations, API docs, and industry-specific resource hubs.

**Gittan implication:** the differentiator is not “we have more collectors.” It is defensible local evidence that turns scattered developer work into reviewable, customer-safe reports. Marketing should translate CLI/local-first features into outcomes: fewer missed billable hours, less admin, stronger trust, and no surveillance. The closest Gittan-native version of Timely's UX promise is: collect local evidence → classify/project-map → review/export with proof.

**Boundary:** avoid copying Timely's SaaS/team promise too literally. Gittan's stronger wedge is local-first, scriptable, evidence-oriented reporting for developers/consultants; team compliance, AutoSheet-style AI allocation, and enterprise dashboards are later-stage or out of scope until the product intentionally moves there.

---

## Competitive boundary: Memory.app overlaps with Gittan

Timely's May 2026 Memory.app update explicitly improves AI-tool tracking for Claude Chat, Claude Cowork, Claude Code, and Codex by reading real window titles and attaching URLs where available. Timely frames the gain as: the timeline tells the truth, and Timely's AI gets better project/note/tag/link predictions.

That is direct evidence-layer overlap with Gittan, not just a downstream app/workflow difference. The practical positioning is therefore:

- **Compete** where the job is “capture and explain AI/dev work context.” Memory.app is trying to solve this with an always-on desktop app; Gittan solves it with a local CLI/evidence engine and source-specific collectors.
- **Differentiate** on local-first inspectability, scriptability, audit/proof output, open-source transparency, and speed of adding niche AI/vibe-coding tools.
- **Avoid front-page copy that sounds like a Timely clone.** Lead with defensible developer evidence, not generic automatic time tracking.

Reference: <https://www.timely.com/product-updates/2026-05-07-memory-app-claude-codex-tracking/>

---

## What Timely's API suggests

The OpenAPI document is broad: time entries, projects, clients, tags, users, teams, reports, OAuth, bulk operations, forecasts/tasks, compliance, day locks, and webhooks. The useful patterns for Gittan are below.

### 1. Time entries are durable workflow objects

Timely's `Hour` model is not just a computed row. It carries:

- actual and estimated duration/cost,
- start/end/timestamp segments,
- billable/billed/locked/draft flags,
- workflow state,
- `external_id`, `external_links`, and linked work-item metadata,
- task/forecast linkage.

**Gittan implication:** keep the local evidence engine, but consider a durable `work unit` / `time entry draft` layer for reviewed output: stable IDs, external links, state, and idempotent export. This maps well to the existing work-unit direction without requiring a hosted API first.

### 2. GitHub evidence needs more than local commits

Timely's public Marketplace copy highlights GitHub memories such as pushed commits, PR comments, issue comments, review comments, branch/tag creation, and PR status changes.

Gittan already has:

- a local Git commit timestamp collector for configured `git_repo` paths,
- a GitHub public activity source via REST API username lookup,
- browser/IDE evidence that can classify GitHub repo pages and local workspace activity.

**Gap to investigate:** a first-class GitHub App source could add private-repo visibility and richer collaboration events that public user activity cannot reliably cover: PR review comments, issue comments, branch/tag events, status transitions, and repository-scoped metadata. That is especially relevant if GitHub Marketplace becomes a distribution target, because GitHub requires the app to provide value beyond authentication.

### 3. Reports are filterable by business dimensions

Timely's report endpoints filter by users, projects, clients, labels, teams, states, billed status, grouping keys, and scope (`totals` vs individual events).

**Gittan implication:** the JSON truth payload already gives automation a strong base. A future query/reporting surface should preserve the current CLI-first model while exposing business filters consistently: client, project, label/tag, billed/export state, and event-vs-total scope.

### 4. Tasks/forecasts connect planned work to logged work

Timely models tasks/forecasts with estimated, planned, logged, and completed duration. Hours can link back to a forecast/task.

**Gittan implication:** this is adjacent to the scheduled→reported bridge and calendar work. The near-term lesson is not “build project management,” but “make planned vs observed vs reported explicit” so users can explain why a final entry exists.

### 5. Bulk import + webhooks imply idempotent integration contracts

Timely supports bulk create/update/delete for hours/events and webhooks for hours, projects, labels, and forecasts. Its create/update shapes include `external_id` and `external_links`.

**Gittan implication:** any future push/sync integration should be draft-first, idempotent, and reversible. `external_id`-style stable IDs and `external_links` for commits/PRs/issues are higher leverage than a broad generic API surface.

### 6. Compliance/capacity/day-locks are later-stage team features

Timely has user capacities, day properties/locks, roles, permissions, teams, and compliance metrics.

**Gittan implication:** these are not solo-first v1 requirements. They are useful vocabulary for future team/admin scope, but they should not pull the near-term product away from local-first trust and low admin overhead.

### 7. Identity model — not `event_id`, but layered IDs

Timely's public OpenAPI spec does **not** define a field named `event_id`. Identity is split across layers (reviewed from Timely's public API document):

| Layer | Timely fields | Role |
| --- | --- | --- |
| **Memory timeline atom** | `entry_ids` (integer array on `Hour`) | Small captured activities from Memory.app that compose logged time |
| **Time segments** | `timestamps[].id`, `timestamps[].entry_ids[]` | Sub-intervals within one logged hour |
| **Approved time entry** | `Hour.id` (int), `Hour.uid` (string), `Hour.external_id` (string) | Durable billing/approval object; API bodies use `{ "event": { ... } }` for create/update — **“event” here means time entry, not a raw observation** |
| **Integration sync** | `external_id` on projects, hours, users, tags, clients, teams | Idempotent mapping to external systems; webhooks include `entity_external_id` |

**Gittan today (local-first):**

| Layer | Gittan identity | Notes |
| --- | --- | --- |
| **Raw observation** (collector) | No explicit ID in runtime dicts; dedup via `(source, timestamp, detail, project)` | Report-time dedup in `core/events.py` |
| **Evidence shadow log** | `fingerprint` — deterministic hash of `(source, observed_at, detail)` **excluding project** | See `core/evidence_record.py`; stable across reclassification |
| **truth_payload session** | `id` = `{day}-{session_index}` | Ephemeral within one report run |
| **truth_payload event** (JSON export) | **No ID field yet** | Only `source`, `timestamp`, `detail`, `project` |
| **Approved export** (future work unit) | Not shipped — planned `work_unit_id` + `external_id` | Aligns with work-unit v2 and partner export idempotency |

**Recommendation (do not copy Timely's naming blindly):**

1. **Observations:** expose existing `fingerprint` as `observation_id` in truth_payload events (cheap, high leverage for ledger diffs and audit).
2. **Approved output:** add `external_id` (and `work_unit_id`) on **reviewed/exportable** rows only — not on every raw collector line.
3. **Source-native IDs:** when a collector has one (e.g. GitHub activity id), store in provenance; otherwise fall back to `fingerprint`.
4. **Avoid** calling approved hours “events” in Gittan export APIs — Timely overloads that term.

See also [`docs/decisions/work-unit-v2-architecture.md`](../decisions/work-unit-v2-architecture.md) §6 (truth_payload evolution) and [`docs/runbooks/timely-gittan-event-ledger-benchmark.md`](../runbooks/timely-gittan-event-ledger-benchmark.md) (same-day comparison procedure).

---

## GitHub Marketplace implications

GitHub Marketplace listings must provide value to the GitHub community and integrate with GitHub beyond authentication. Listings also need support/contact links, privacy policy, pricing plan, working listing assets/screenshots, and marketplace purchase webhook handling where applicable.

For Gittan, the most compatible shape appears to be:

1. **Local-first core remains the product truth.** No forced cloud timeline upload.
2. **GitHub App companion adds consented GitHub evidence.** Fine-grained permissions, private repo support where authorized, and event metadata that local Git alone cannot see.
3. **CLI/report output remains review-first.** The app should help produce defensible local reports; it should not silently submit time.
4. **Marketplace listing sells the GitHub-specific value.** Example positioning: “privacy-first GitHub time evidence for consultants and teams who need defensible reports.”

---

## Candidate next slices

1. **Benchmark slice:** export same-day event ledgers from two trackers and classify differences as missed evidence, duplicate/overlap, session-gap policy, source coverage, or noise filtering. Do not optimize on total hours alone. Procedure: [`docs/runbooks/timely-gittan-event-ledger-benchmark.md`](../runbooks/timely-gittan-event-ledger-benchmark.md).
2. **AI-tool evidence benchmark:** compare Gittan collectors against Memory.app's Claude/Codex title+URL capture: specificity, privacy posture, source explainability, and project-attribution lift.
3. **GitHub App source spec:** define required GitHub permissions/events, private repo handling, webhook vs polling, token storage, and how events map into Gittan's source model.
4. **External link model:** ensure work units / report JSON can carry commit, PR, issue, and review URLs as structured links rather than only text detail.
5. **Marketplace readiness checklist:** support/privacy/pricing/listing assets plus a clear “value beyond auth” statement.
6. **Report filter vocabulary:** align future query/export flags with project, client, label, billed/export state, and event-vs-total scope.

---

## References

- Timely GitHub Marketplace listing: <https://github.com/marketplace/timely-time-tracking-and-planning>
- Timely Memory.app Claude/Codex update: <https://www.timely.com/product-updates/2026-05-07-memory-app-claude-codex-tracking/>
- GitHub Marketplace listing requirements: <https://docs.github.com/en/apps/github-marketplace/creating-apps-for-github-marketplace/requirements-for-listing-an-app>
- GitHub Apps vs OAuth Apps: <https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps>
- [`docs/inspiration/similar-repos-checklist.md`](../inspiration/similar-repos-checklist.md) — commercial competitor index (Timely alternatives hub) and OSS repo scan log
- [`docs/ideas/partner-briefs/`](../ideas/partner-briefs/) — working partner hypotheses (Timely, Harvest)
- [`docs/runbooks/timely-gittan-event-ledger-benchmark.md`](../runbooks/timely-gittan-event-ledger-benchmark.md) — same-day ledger diff before partner outreach
