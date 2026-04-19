# Substack draft — Data & AI Stockholm (Gittan origin story)

**Channel:** [Data & AI Stockholm](https://www.dataaistockholm.com/) (community newsletter / Substack)  
**Intent:** Expand the speaker manuscript into a readable story—**more detail than the five beats**, but **not a technical deep dive**. Readers should understand *why* the project exists and *what* it promises, without needing to care about file paths or database names.

**Language:** This draft is in **English** (common for Nordic data/AI audiences). If the edition is Swedish-first, translate freely—keep the emotional beats, shorten sentences.

---

## Alignment with DAIS Author Guidelines

*Source: DAIS Author Guidelines (community PDF). This section is a **submission checklist**—keep it when you paste into Substack only if you want; otherwise delete before publish.*

| Guideline | How this draft maps |
|-----------|---------------------|
| **Clear connection to data and AI in practice** | Personal data pipeline (traces on disk → reconciled hours); applied AI (agents as iteration partners); product path from prototype toward something reviewable. |
| **Topics the community cares about** (pick what fits) | Fits especially: *Developing AI-powered products from prototyping to scaling*; *Data security and responsible AI usage* (local-first, no raw-day upload by default); *Practical solutions to common data challenges* (honest time reconstruction); *CI/CD / pipelines* in the “harness” sense (tests + repeatable workflow). |
| **Structure: introduction, body, conclusion** | The **Body (copy-paste)** block below uses explicit **Introduction** / **Body** / **Conclusion** headings you can keep or flatten to H2s in Substack. |
| **Author’s own perspective** (≥1 insight) | Sections *Reflection*, *What I’d repeat*, and the closing **discussion question**. |
| **At least one visual** where it makes sense | See **Visuals (required for DAIS)** below—**Azar (DAIS team)** can advise if you are unsure. |
| **Purpose: insight, reflection, discussion** | Ending invites community response; trade-offs called out (trust vs convenience, multi-signal vs monolithic metrics). |

**Examples of tone and structure:** browse previous DAIS articles on the community Substack (link is usually on [dataaistockholm.com](https://www.dataaistockholm.com/) under newsletter / publications).

---

## Visuals (required for DAIS)

Guidelines ask for **at least one** visual when it helps. Ideas that match this story without exposing private data:

1. **Simple flow:** boxes *Traces (browser, IDE, mail, git)* → *Rules / project mapping* → *Sessions & hours* → *Optional export*.  
2. **Before/after:** “monolithic block: Terminal 4h” vs “contextual sessions tied to projects.”  
3. **Screenshot:** blurred or synthetic `gittan report` output or `gittan doctor` summary—readable, not a wall of JSON.

If unsure, contact **Azar** in the DAIS team (per guidelines).

---

## Suggested Substack metadata

**Working title:** *I Used My Browser History as a Diary for 15 Years—Then I Built a Time Tracker*

**Subtitle (optional):** *A local-first tool born from invoice panic, coworker banter, and curiosity in the agent era.*

**Author byline:** Fill in (you / DAIS Engineering as appropriate for the Substack account).

**Hero image:** Use the **visual** above (flow or before/after)—hero + one inline image is enough.

---

## Body (copy-paste into Substack)

### Introduction

**What this is about.** This piece is a story from practice: how messy, human work—research, coding, email, thinking in chat—runs into a very unglamorous data problem at month-end: **reconstructing time** in a way you can defend. It connects to **data and AI** because the path went through **local signals**, **iteration with agents**, and a product choice about **trust** (what leaves your machine, and when).

For more than **fifteen years**, my browser history has been a kind of **external memory**. Not because I’m nostalgic about URLs, but because the alternative—reconstructing a workday from feelings—is unreliable. On a Tuesday in March, *what did I actually do*? The honest answer is often scattered across tabs, terminals, and half-finished notes.

That habit sounds eccentric until you bill by the hour. Then it becomes a **professional survival skill**.

---

### The thirty-second prototype

The project that became **Gittan** did not start as a product. It started as a conversation.

A colleague and I were complaining about the same old problem: our days are **multi-modal**. Research in the browser, implementation in the editor, thinking in a chat, follow-ups in email. Classic time trackers want you to press “start” and “stop,” as if focus were a light switch. We knew that wasn’t how the work worked.

Roughly **thirty seconds later**, there was a **small script** in a **local repository** on my machine—not a roadmap, not a brand, just a pragmatic experiment. The earliest commits lived in that separate prototype folder before the work consolidated into the open repository you can see today. The point isn’t the folder name; the point is that **serious systems can begin as embarrassingly small code**.

### Same client, new assignment

Soon after, I was back with a **familiar client** on a **new assignment**. The work was interesting. The administration was familiar in a worse way: at some point, someone would ask for an account of time—and I would need to stand behind it.

That’s a different pressure than “tracking productivity.” It’s closer to **accounting**. You are not optimizing your soul; you are trying to write a line item that won’t embarrass you in a review.

### Month-end, curiosity, and the agent loop

Then came **month-end**.

If you’ve ever stared at a blank row on an invoice and felt a quiet dread, you know the feeling. It’s not laziness. It’s **epistemic fatigue**: the brain wants a story, and the calendar wants numbers.

Two things helped me at that stage—more than any single tool.

First, **curiosity pays off more than ever**. If you hear something sharp on a podcast—an insight about attention, context switching, or how teams measure work—**bring it to an agent**. Not as a magic oracle, but as a **thinking partner**: “Here’s the constraint; here’s what I tried; here’s what feels wrong.” The goal isn’t poetry. The goal is to **iterate** until you have something testable: a script, a failing test that should pass, or a sharper question.

Second, I asked a boring, scary question about the prototype: **can this move up one level**—from “clever hack” to “something I’d trust when someone asks”?

That question is where amateur tooling separates from something you can maintain. It’s also where **automation** stops being a party trick and becomes **engineering**.

### What Gittan is (in plain language)

**Gittan** (open source: `timelog-extract`) turns **traces you already leave on your machine** into **project hours** and, when you want it, **review-ready output**—including optional invoice-style exports.

The default posture is **local-first**: your machine, your files, your choice of sources. We are not building a business model around uploading your raw day to our cloud “so we can help you.” If you want to share proof, you export what you choose.

If you want a single mental model: **dig where you stand**. Instead of asking you to become a disciplined clock-puncher, the tool meets the workflow where it already happens—browser, IDE, mail, commits, worklogs—then helps you reconcile that into honest hours.

### Enough technical taste to be real (without drowning anyone)

If you’re technically inclined, here is the gentle version of “how,” in one breath.

Modern work leaves **multiple imperfect signals**. A blunt “screen time” total treats “Terminal” like a brick. But the interesting question is often **context**: what were you working on, not merely that a window was open. Gittan combines **local** signals—things already on disk—with **rules you control** so sessions can map to projects. The implementation details vary by platform and source; the point is **composition**, not a single oracle sensor.

If that paragraph felt like enough, stop reading the engineering part. The article isn’t trying to teach you the schema. It’s trying to explain why **multi-signal** beats **monolithic guilt**.

### What a focused few weeks looked like (numbers without chest-thumping)

After a period of intensive work—on the order of **weeks**, not years—the project accumulated **tens of thousands of lines** of Python, **hundreds of automated tests**, and a steady drumbeat of commits. I’m cautious about turning that into a leaderboard; software isn’t “more correct” because it’s bigger.

The meaningful claim is narrower: the codebase exists because **trust** required it—trust that refactors don’t silently break collectors, trust that edge cases get caught before they become invoice edge cases.

If you’re comparing notes with your own agent-assisted projects, the lesson isn’t the exact totals. The lesson is that **a harness** (tests, repeatable commands, clear docs) is what lets curiosity scale without turning into chaos.

#### Reflection (personal)

What shifted for me was not “more automation,” but **where I demand evidence**. If a pipeline can’t survive a skeptical reader—future me, a client, or a finance review—it is still a hobby. Framing **invoice readiness** as a design constraint early saved me from polishing the wrong layer.

**Trade-offs I sit with:** combined local signals are powerful and imperfect; “honest hours” is still an interpretation, not a physical law. The goal is to make assumptions **visible** and **adjustable**, not to pretend a single score captured your day.

---

### Conclusion / discussion

#### What I’d repeat

- **Treat curiosity as a workflow.** A half-formed idea from a podcast or a hallway chat is a valid input—if you’re willing to iterate with an agent until it becomes something concrete.
- **Treat local-first as product ethics.** The data is already sensitive; the architecture should reflect that.
- **Treat “invoice readiness” as a design constraint.** If the output can’t survive a skeptical reader, it’s not finished—no matter how clever the pipeline feels.

#### Community and a practical next step

If this resonates, you’re exactly the kind of reader **[Data & AI Stockholm](https://www.dataaistockholm.com/)** exists for: people who care about **data**, **models**, and **the human mess around them**—shipping, governance, and the gap between demo and daily use.

Try the tool if you want a hands-on perspective:

- **Site:** [gittan.sh](https://gittan.sh/)  
- **Code:** [github.com/mbjorke/timelog-extract](https://github.com/mbjorke/timelog-extract)  
- **Quick install (macOS-friendly):** use [pipx](https://pypa.github.io/pipx/), then `pipx install timelog-extract`, then `gittan -V`. Other paths live in the repository README.

**Question for the community:** When you reconstruct a workweek under pressure—billing, compliance, or planning—which **signal** do you trust least (calendar, chat, git history, ticket system, memory), and what would you want a tool to **never** do with your data? Comments welcome—this is as much about norms as about code.

---

## Maintainer checklist before publishing

- [ ] **DAIS:** At least one **visual** uploaded; ask **Azar** if stuck (per DAIS guidelines).
- [ ] **DAIS:** Clear **data/AI in practice** thread in the intro (kept above—trim if Substack preview is long).
- [ ] Replace placeholder byline / company voice if the piece runs under the **community** account vs **personal** byline.
- [ ] Confirm whether the **29 April** demo or talk should be mentioned explicitly (add one sentence + link when details are public).
- [ ] Re-run rough stats if you quote lines/commits/tests (`stage-demo-speaker-notes.md` has commands).
- [ ] If the newsletter is **Swedish**, translate the title so it stays conversational (avoid literal calques that sound like marketing English).
- [ ] Remove the **Alignment** / **Visuals** sections at the top of this file from the pasted Substack post (they are author-only).

---

## Related in-repo drafts

- Short product-forward draft: [`dais-insights-human-first-automation-2026-04-15.md`](dais-insights-human-first-automation-2026-04-15.md)
- Speaker beats + stats: [`stage-demo-speaker-notes.md`](stage-demo-speaker-notes.md)
