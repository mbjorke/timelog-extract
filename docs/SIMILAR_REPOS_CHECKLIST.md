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