# Gittan: The Privacy-First Auditor for the AI Age

This file is a **short public manifesto** (e.g. Patreon, landing snippets). The full product vision, boundaries, and metrics live under `docs/` — see **`docs/VISION_DOCUMENTS.md`** for hierarchy and precedence. Draft Patreon tiers, taglines, and positioning notes live in **`docs/PATREON_POSITIONING.md`**. If anything here disagrees with `docs/GITTAN_VISION.md` or `docs/V1_SCOPE.md`, **update this file** to match those (they are authoritative).

## The Problem
As developers, we are living in the golden age of "AI Flow." Between Cursor, Claude, and Gemini, we are building faster than ever. But there’s a hidden cost: **we are losing track of our time.**

When you switch between five different AI chats and three IDE windows in an hour, traditional time trackers fail. You end up guessing your hours at the end of the month, usually under-billing yourself because you "can't quite remember" if that 2-hour session was for Project A or Project B.

## The Gittan Vision
**Gittan** (Swedish for "The Git" or a friendly neighborhood auditor) is built to find your lost hours. 

Unlike other tools, Gittan follows three core commandments:

1.  **Local-first, user in control:** Core reporting does **not** require you to upload your raw activity to *our* servers. Primary traces (IDE, browser, mail, Screen Time, local CLIs) stay on your machine unless **you** choose otherwise. Optional **cloud-agent** visibility (below) uses **your** credentials and **provider APIs**—not a Gittan data lake.
2.  **Density-Aware Precision:** Gittan doesn't just see that a window was open. It looks at the *pulse* of your activity—how many times you prompted Claude, how many checkpoints you saved in Cursor, and how many docs you read in Chrome.
3.  **Developer-First UX:** Gittan is a tool built by developers, for developers. It lives in your terminal and your IDE, not in a distracting web dashboard.

## Local truth, cloud-aware work
Modern work is not only local. When you **dispatch work to cloud agents**, a growing share of value is created **outside** your repo: runs, artifacts, and cost live with the provider. Gittan’s direction is to reconstruct **billable truth** across **both** human and agent activity: **local signals** for what happened on your machine, plus **optional, consent-based connectors** that pull **metadata** (time, job identity, cost, links to outputs) from cloud agent platforms—so you can answer what **you and your agents** produced, not only what landed in git.

That does **not** mean sending everything to a third-party “tracking cloud.” It means **the same privacy stance**—**minimal data, explicit scope, user-approved** channels—applied to **remote** work as well as local.

## How It Works
Gittan aggregates "signals" from your local system:
*   **AI IDEs:** Cursor logs and checkpoints.
*   **AI CLIs:** Claude Code, Gemini CLI.
*   **Web Activity:** Specific chat URLs (Claude.ai, Gemini) and documentation visits.
*   **Communication:** Apple Mail headers (sender/receiver) to catch that "quick 10-minute email" that turned into an hour.
*   **System Truth:** Cross-references everything with macOS Screen Time to help the timeline stay coherent.
*   **Cloud agents (directional):** Optional source adapters that attach **job-level** evidence from agent platforms (runs, spend, deliverables) where APIs allow—without replacing local-first defaults.

## Why Support Gittan on Patreon?
Gittan is **source-available** (see repository `LICENSE` and `docs/SPONSORSHIP_TERMS.md`) and privacy-focused. By becoming a Patron when your use requires it, you are supporting:
*   **New Source Adapters:** Faster integration for new AI tools as they launch.
*   **IDE Experience:** The optional Cursor extension and related UX — the **CLI remains the primary v1 path**; see `docs/VISION_DOCUMENTS.md` and `README.md`.
*   **Independence:** Keeping Gittan free from venture capital and corporate data-mining.

---
**Stop guessing. Start billing. Gittan knows.**
