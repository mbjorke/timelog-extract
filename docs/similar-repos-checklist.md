# Similar repositories checklist

Use this when evaluating GitHub (or other) projects that might overlap with **Timelog Extract**: Cursor-first delivery, local-only aggregation, multiple AI/dev activity sources, optional invoice PDF, macOS primary for v1. See also `V1_SCOPE.md` and `PRIVACY_SECURITY.md`.

## Tier A — Quick filter (README, license, activity)


| Question                                                                               | Why it matters                                                                                                               |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Local-only by default?** Any required cloud, sync, or remote API for core reporting? | V1 is explicitly local-first; an OSS client for a SaaS backend is a different product.                                       |
| **License** (MIT, Apache-2.0, AGPL, etc.)                                              | Determines whether you can fork, redistribute, or reuse patterns in your product.                                            |
| **Maintained?** Last meaningful commit, open issues and PRs                            | Avoid anchoring on abandonware.                                                                                              |
| **Scope match**                                                                        | "Git stats dashboard" vs "multi-source timelog + invoicing" — partial overlap is fine if you know what you still must build. |


## Tier B — Architecture fit (skim code or issues)


| Dimension           | What to check                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data model**      | Per-event vs daily rollups; project/customer tagging; how classification works (regex, ML, manual).                                                        |
| **Source coverage** | Ingestion for v1 sources: Cursor, Codex index, AI CLI logs, tracked URLs, worklog-style files (`TIMELOG.md`). Gaps show where you extend vs stay separate. |
| **Privacy posture** | Consent and opt-in, what is read from disk, what is logged — align with sensitive sources off by default and redaction rules.                              |
| **Outputs**         | CSV, Markdown, PDF, APIs — you care about report plus optional invoice PDF and editor-friendly flows.                                                      |
| **Extensibility**   | Plugin architecture vs monolithic script — affects contribute upstream vs fork.                                                                            |


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

