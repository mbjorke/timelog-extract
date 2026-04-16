# DAIS Insights Draft (Code-Verified)

**Headline:** Human-First Automation: Engineering a Multi-Signal Time Tracker for the AI Era

**Author:** DAIS Engineering

At DAIS, we often talk about building "human-first" AI. But as developers and engineers, our own "human" experience is often bogged down by a task that feels decidedly anti-human: **manual time tracking.**

As our workflows become "AI-augmented," the struggle has intensified. On any given day, we're jumping between Cursor, the terminal with Claude Code, browser-based research, and Slack huddles. Trying to reconstruct at the end of the month whether you spent 15 minutes or 2 hours on a specific API bottleneck is a cognitive nightmare.

That's exactly why we built **Gittan (timelog-extract)**.

## The Data Engineering Approach: Digging Where You Stand

Instead of relying on manual timers or blunt-force Screen Time apps, I took a data-first approach. On macOS, we have a wealth of local signals that, when combined, tell a complete story of our workday.

Gittan doesn't rely on a single source. Instead, it aggregates multiple local event streams:

- **Screen Time Metadata:** Extracting app usage patterns from the macOS `knowledgeC.db`.
- **Browser Context:** Pulling URL fragments and **page titles** from local Chrome history to provide project-specific context.
- **AI/IDE Logs:** **Parsing local logs and metadata** from tools like **Claude Code**, **Gemini CLI**, **Cursor logs**, and **Cursor checkpoints**.

## Beyond the "Monolith" Block

Traditional trackers see "Terminal" or "Browser" as monolithic blocks of time. By combining these signals, Gittan creates a richer event stream that understands the context of the work.

- **AI Workflow Visibility:** It tracks local activity from modern AI tools that traditional trackers often miss.
- **Automatic Project Mapping:** It matches these local traces (paths, log context, and keywords) to configurable project rules.
- **Invoice-Ready Output:** It converts these raw events into session-based hours with configurable rounding and optional invoice PDF generation.

## A Call for Peer Review

Last week, I sent out my first real-world invoice generated entirely by Gittan's data. For the first time, time tracking felt like a "win" rather than a chore.

The project is now in open-source alpha, and I'm looking for feedback from the DAIS community. As people who understand data pipelines and AI integration, your perspective on how we can better "track the untrackable" is invaluable.

- **Project Site:** [gittan.sh](https://gittan.sh/)
- **GitHub:** [mbjorke/timelog-extract](https://github.com/mbjorke/timelog-extract)
- **Quick Start:** `pip install timelog-extract` (macOS-first)
