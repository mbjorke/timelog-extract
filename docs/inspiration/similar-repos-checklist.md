# Similar repositories and time-tracker landscape checklist

Use this when evaluating **open-source / GitHub projects** and **commercial time trackers** that might overlap with **Gittan (Timelog Extract)**: CLI-first delivery, local-only aggregation, multiple AI/dev activity sources, optional invoice PDF, macOS primary for v1.

See also [`docs/product/v1-scope.md`](../product/v1-scope.md), [`docs/security/privacy-security.md`](../security/privacy-security.md), and [`docs/ideas/timely-api-marketplace-benchmark.md`](../ideas/timely-api-marketplace-benchmark.md).

**Two tracks:**

1. **OSS repos** — fork/learn/ignore decisions (Tier A–C below).
2. **Commercial trackers** — market map, buyer segments, and differentiation (working queue; serious analysis later).

---

## Tier A — Quick filter (README, license, activity)

| Question | Why it matters |
| --- | --- |
| **Local-only by default?** Any required cloud, sync, or remote API for core reporting? | V1 is explicitly local-first; an OSS client for a SaaS backend is a different product. |
| **License** (MIT, Apache-2.0, AGPL, etc.) | Determines whether you can fork, redistribute, or reuse patterns in your product. |
| **Maintained?** Last meaningful commit, open issues and PRs | Avoid anchoring on abandonware. |
| **Scope match** | "Git stats dashboard" vs "multi-source timelog + invoicing" — partial overlap is fine if you know what you still must build. |

## Tier B — Architecture fit (skim code or issues)

| Dimension | What to check |
| --- | --- |
| **Data model** | Per-event vs daily rollups; project/customer tagging; how classification works (regex, ML, manual). |
| **Source coverage** | Ingestion for v1 sources: Cursor, Codex index, AI CLI logs, tracked URLs, worklog-style files (`TIMELOG.md`). Gaps show where you extend vs stay separate. |
| **Privacy posture** | Consent and opt-in, what is read from disk, what is logged — align with sensitive sources off by default and redaction rules. |
| **Outputs** | CSV, Markdown, PDF, APIs — you care about report plus optional invoice PDF and editor-friendly flows. |
| **Extensibility** | Plugin architecture vs monolithic script — affects contribute upstream vs fork. |

## Tier C — Product and operations (if you would depend on it)


| Dimension              | What to check                                                                  |
| ---------------------- | ------------------------------------------------------------------------------ |
| **Platform**           | macOS-first vs cross-platform assumptions (paths, sandboxing, extension APIs). |
| **Editor integration** | VS Code vs Cursor-specific — estimate porting cost.                            |
| **Test and CI**        | Tests and reproducible runs reduce risk when merging your sources.             |
| **Distribution**       | PyPI, marketplace, or clone-and-run — affects trials and adoption.             |


## Red flags

- Core flow requires account creation or a remote backend for normal use.
- No credible story for **AI session logs** or IDE artifacts — only `git log` or crude uptime.
- Invoicing is a separate product with no shared time model.
- Heavy telemetry or opaque "anonymized" upload defaults.

## How to use

1. **Tier A** cuts the long list down.
2. **Tier B** answers fork vs learn-from vs ignore.
3. **Tier C** only if you might build **on** the project, not just borrow ideas.

## Tier A scan log

Dated snapshots of a Tier A pass against public GitHub repos. Use the same criteria as **Tier A — Quick filter** above. **Next step:** pick candidates for Tier B after each scan.

### 2026-04-09

**Method:** GitHub repository search (multiple queries: local / developer time tracking, `gtimelog`, ActivityWatch, Kimai, self-hosted WakaTime-compatible servers, AI CLI usage). Results that were clearly unrelated (wrong domain) were discarded.

| Repository | Local-first default? | License | Maintenance (signal) | Scope vs Timelog Extract |
|------------|----------------------|---------|------------------------|---------------------------|
| [ActivityWatch/activitywatch](https://github.com/ActivityWatch/activitywatch) | Yes — local stack; sync optional | MPL-2.0 | Strong — active, large community | Partial — window/app/AFK-style automation; not AI-session + Cursor + `TIMELOG.md` fusion; invoicing not in core |
| [gtimelog/gtimelog](https://github.com/gtimelog/gtimelog) | Yes — file-based | GPL-2.0 | Moderate — commits into 2025 | Partial — worklog-style manual time; no multi-source AI ingestion or invoice PDF |
| [kimai/kimai](https://github.com/kimai/kimai) | No — self-hosted web app (on-prem OK, not “no server”) | AGPL-3.0 | Strong | Partial — timesheets + invoicing; different stack and UX; not local log aggregation |
| [Hitheshkaranth/OpenTokenMonitor](https://github.com/Hitheshkaranth/OpenTokenMonitor) | Mostly — optional live API advertised | MIT | Early — small repo, recent activity | Narrow — AI CLI token/cost monitoring; not customer time reports |
| [mujx/hakatime](https://github.com/mujx/hakatime) | No — self-hosted WakaTime-compatible server | Unlicense | Moderate — last push 2024 | Partial — IDE time via WakaTime protocol; not Cursor/Codex log fusion or invoices |
| [Waishnav/Watcher](https://github.com/Waishnav/Watcher) | Yes — Linux screen-time | MIT | Some activity | Weak — Linux screen time; different OS focus |

**Summary:** No single public repo in this pass matched the full Timelog Extract v1 combo (local-only core, multi-source AI/dev logs, Cursor path, optional invoice PDF). Closest *clusters*: local automated activity (ActivityWatch), worklog discipline (gtimelog), web invoicing (Kimai), WakaTime-server ecosystem (hakatime), AI usage widgets (OpenTokenMonitor).

---

## Commercial time-tracker landscape (Timely alternatives lens)

**Status:** Working market map — **not** neutral analysis. Timely's pages are SEO/competitor capture; treat them as a **curated index of who shops in this category** and how Timely frames differentiation. Serious product analysis comes later (primary sources, trials, API/docs, pricing).

**Source (reviewed 2026-07-02):** [Timely — all alternatives](https://www.timely.com/all-alternatives/) and linked `/alternatives/*` comparison pages.

### Why this matters for Gittan

Timely's alternatives hub is effectively a **lead list**: agencies, consultants, and service teams comparing tools for billing accuracy, admin reduction, and privacy. That overlaps Gittan's aspirational buyers (solo consultants and dev-heavy billers) even when Gittan is **not** trying to become a full team SaaS suite on day one.

Use this section to answer:

1. **Who else is in the consideration set** when someone wants "automatic" or "defensible" time reporting?
2. **Which feature axes buyers expect** (privacy, automation, approval, invoicing, capacity)?
3. **Where Gittan should not compete head-on** (team capacity, native invoicing, PM OS) vs **where CLI/local evidence is the wedge** (developer AI-tool traces, inspectable proof, scriptable export).

### Timely's comparison dimensions (feature matrix)

Timely groups competitors under five headings on [all-alternatives](https://www.timely.com/all-alternatives/). Useful as a **buyer checklist** when scoring Gittan later — not as a scorecard to copy verbatim.

| Group | Features Timely highlights |
| --- | --- |
| **Privacy** | User privacy, data encryption |
| **Accuracy** | Automatic capture, AI suggestions |
| **Ease of use** | Stop/start timer, calendar view, locked time entries, time rounding, custom timesheet statuses, timesheet approval |
| **Reporting** | Customized reports, live reports, invoices, budgets, high-quality data |
| **Capacity** | Wide integrations, employee capacity, tasks, group vs non-group messaging |

**Timely's recurring story:** manual timers lose hours; background automatic capture + AI-drafted entries + approval workflow scales better; privacy-first (no screenshots/keylogs) vs surveillance-heavy tools.

**Gittan draft contrast (for later validation):** evidence engine + human approval + local inspectability — not a hosted timeline, not team capacity planning, not native invoicing. Closest overlap with **automatic/memory** tools (Timely, Memtime, RescueTime, DeskTime); complementary or export target for **manual timer + billing** tools (Toggl, Harvest, Clockify, Paymo, QuickBooks).

### Competitor index (Timely-hosted comparisons)

Direct comparison pages linked from Timely's hub:

| Tool | Timely comparison page | Draft category |
| --- | --- | --- |
| Toggl | [alternatives/toggl](https://www.timely.com/alternatives/toggl/) | Manual-first timer; strong freelancer UX |
| Clockify | [alternatives/clockify](https://www.timely.com/alternatives/clockify/) | Budget timer + admin controls; free tier |
| Harvest | [alternatives/harvest](https://www.timely.com/alternatives/harvest/) | Time + invoicing for agencies |
| Memtime | [alternatives/memtime](https://www.timely.com/alternatives/memtime/) | Automatic desktop memory (Microsoft ecosystem) |
| RescueTime | [alternatives/rescuetime](https://www.timely.com/alternatives/rescuetime/) | Personal productivity / automatic app time |
| DeskTime | [alternatives/desktime](https://www.timely.com/alternatives/desktime/) | Automatic + attendance/surveillance-leaning positioning |
| TimeCamp | [alternatives/timecamp](https://www.timely.com/alternatives/timecamp/) | Automatic + billing; mid-market |
| ClickUp | [alternatives/clickup](https://www.timely.com/alternatives/clickup/) | Work OS / PM with embedded time |
| Monday.com | [alternatives/monday-com](https://www.timely.com/alternatives/monday-com/) | Work OS / PM with embedded time |
| Paymo | [alternatives/paymo](https://www.timely.com/alternatives/paymo/) | PM + time + invoicing |
| QuickBooks Time | [alternatives/quickbooks](https://www.timely.com/alternatives/quickbooks/) | Accounting suite + time |

Featured in Timely's **summary matrix** on the hub (subset): ClickUp, Clockify, DeskTime, Harvest, Monday.com.

### Commercial scan queue (Tier A — not yet analyzed)

**Next step:** for each row, run a short pass: local-first option?, developer/AI evidence?, pricing entry, privacy stance, export/API, and "Gittan relationship" (compete / complement / ignore). Promote strong candidates to Tier B (trial + docs + API skim).

| Tool | Timely's headline contrast (paraphrase) | Likely Gittan buyer overlap | Gittan relationship (draft) | Analysis |
| --- | --- | --- | --- | --- |
| **Toggl** | Still timer-first; reminders/idle ≠ full automatic | High — freelancers, agencies, consultants | Complement — export/report upstream; many devs already use it | Queued |
| **Clockify** | Cheaper, more admin/surveillance options; less automatic | Medium — ops-heavy teams | Complement or ignore — different buyer (admin control) | Queued |
| **Harvest** | Established agency billing; manual discipline | High — consultants who invoice hours | Complement — evidence → approved hours → Harvest invoice | Queued |
| **Timely** | Reference automatic + AI + privacy SaaS | High — same "missed billable hours" pain | Compete on evidence layer (Memory.app); see benchmark doc | Partial — [`timely-api-marketplace-benchmark.md`](../ideas/timely-api-marketplace-benchmark.md) |
| **Memtime** | Microsoft-integrated automatic timeline | Medium — knowledge workers on M365 | Compete — automatic desktop memory | Queued |
| **RescueTime** | Productivity analytics, not client billing | Low–medium — personal focus | Learn-from — automatic app classification | Queued |
| **DeskTime** | Automatic + attendance; surveillance risk | Medium — employers | Ignore primary — trust mismatch | Queued |
| **TimeCamp** | Automatic + invoices; mid-market | Medium | Complement — billing sink | Queued |
| **ClickUp** | Time inside PM OS | Medium — teams living in ClickUp | Ignore core — different product gravity | Queued |
| **Monday.com** | Time inside PM OS | Medium — teams living in Monday | Ignore core — different product gravity | Queued |
| **Paymo** | PM + time + invoice bundle | Medium — small agencies | Complement — billing/PM sink | Queued |
| **QuickBooks** | Accounting-first time | Medium — SMB bookkeeping | Complement — accounting export | Queued |

### Buyer segments visible on Timely's pages (hypothesis)

Timely's social proof on the alternatives hub skews toward **Application Consultant**, **Cloud & Infrastructure Consultant**, agencies, and ops-led teams — i.e. people who bill time and care about admin + trust. That aligns with Gittan's **consultant / solo dev** story more than with pure employee surveillance buyers.

**Later analysis should validate:** which segments actually tolerate CLI-first workflow, and which need a GUI or existing SaaS integration on day one.

### Related docs

- [`docs/ideas/timely-api-marketplace-benchmark.md`](../ideas/timely-api-marketplace-benchmark.md) — Timely API, Memory.app overlap, GitHub Marketplace
- [`docs/ideas/partner-briefs/`](../ideas/partner-briefs/) — Timely and Harvest partner hypotheses
- [`docs/runbooks/timely-gittan-event-ledger-benchmark.md`](../runbooks/timely-gittan-event-ledger-benchmark.md) — same-day ledger diff before outreach
- [`docs/ideas/opportunities.md`](../ideas/opportunities.md) — product bets and go-to-market notes

