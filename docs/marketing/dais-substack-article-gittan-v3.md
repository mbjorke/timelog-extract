# I wanted to know where my hours went. AI made that harder.

**From scattered local traces to accountable evidence in the age of agentic work**

I did not start Gittan because I wanted to build a time-tracking product.

I started it because month-end invoicing stressed me out. Not because I had not
worked, but because I had to reconstruct messy weeks from memory, browser tabs,
calendar fragments, commits, and a vague sense of having been very busy.

AI has made that problem sharper.

A normal workday can now move through Cursor, Claude Code, GitHub, terminal
sessions, browser research, docs, email, and short-lived agent experiments. It
is rarely one clean task at a time. I may have several agents and sessions in
motion, across several projects, with each 15-minute stretch touching three to
five different threads just to move them all forward.

The question is no longer just "what did I do?"

It is:

**Which work belonged to which project, and can I explain why?**

That is the question Gittan is trying to answer.

## The naive advantage

For a long time, I viewed my lack of traditional mastery as a liability.

I am not the world's best programmer. I am still uncomfortable reading a
balance sheet, despite years as a treasurer. My mental math peaked at age 20 and
has been in a steady decline ever since.

But in the AI era, that naivety can be useful. I am not attached to one elegant
implementation style. I care whether the system helps me make a better decision
when the stakes are real.

The decision I needed help with was simple:

**Can I trust this time report enough to invoice from it?**

## Why this became a data problem

Traditional time tracking assumes linear work and manual discipline:

start timer, stop timer, classify task.

Real work does not look like that. Especially not agentic work.

You read an issue, ask an AI agent to inspect a branch, review a pull request,
check a browser tab, fix a test, answer a message, then come back to the
original problem with half the context living in tools you did not consciously
log.

So I started digging where I stood.

Gittan treats local traces as external memory:

- IDE and AI-agent logs,
- browser history,
- Cursor checkpoints,
- worklogs,
- GitHub activity,
- project rules you control.

The goal is not surveillance. The goal is a report you can inspect.

## Collection was not the hard part

The first bet was that more local signals would produce better reports. That is
partly true.

App-level data like "Terminal 3h" is almost useless for project attribution.
Browser history, repo paths, commits, and AI logs add much better context.

But collection was not the hardest problem.

The hard part is turning raw activity into a project config a person can trust.
If the rules are too broad, hours move to the wrong customer. If setup is too
manual, no one reaches value. If the tool says "invoice-ready" too early, it
overclaims.

That realization changed the story.

The real product problem is:

**How do we get from observed activity to classified time, and only then to
human-approved invoice time?**

## The truth standard I wish existed

Inside the project, I have started calling this the Timelog Truth Standard.

It separates three things that are easy to blur:

1. **Observed time**: what the machine can see.
2. **Classified time**: what rules and evidence suggest.
3. **Approved invoice time**: what a human explicitly accepts.

Those are not the same thing. The distinction matters.

A report can be useful before it is final. A classifier can be helpful without
being trusted blindly. A local trace can be evidence without becoming a billing
decision.

That is the design center now: evidence first, suggestions second, human
approval before writes.

## Building with a meticulous peer

The technical work has not been solo.

I orchestrate AI tools, including CodeRabbit as a strict reviewer. It catches
small bugs, risky assumptions, and details I would otherwise miss.

One detail I did not expect is how distinct these tools feel in practice. The
agents are starting to develop recognizable personalities.

CodeRabbit has become "the rabbit" in my head: strict, fast, sometimes a little
dramatic, and useful precisely because it does not care about my feelings. In
one pull request, its review summary arrived as a short poem about extracted
doctor rows and URL-encoded keys:

> In a garden of diffs, with thread-safe care,
> I've hopped through the code, fixed bugs everywhere—
> URL-encoded keys and toggl's now sound,
> Doctor rows extracted, helpers are found!
> The API now clear, with *all* in place,
> This PR's a leap forward at lightning-quick pace!

It was funny, but also clarifying.

Gittan is starting to get a personality too. The CLI is not just dumping rows;
it is learning to speak in a calm, inspectable way about evidence, gaps, and
next steps.

This is no longer just about "using AI to code faster." It is about managing a
small team of specialized tools, each with a role.

That speed is powerful, but it creates a second problem: accountability has to
scale with output.

Tests, runbooks, review gates, and explicit product language are not overhead in
that environment. They are how the work stays understandable.

## What the system actually does

Gittan is a local-first Python CLI with a layered pipeline:

- **Source collection**: read local traces from places work already leaves marks:
browser history, IDE/AI logs, worklogs, and GitHub activity.
- **Normalization**: turn messy source-specific records into comparable events
with timestamps, sources, and context.
- **Sessionization**: group nearby events into work sessions so the report
reflects how work actually happened, not just raw app usage.
- **Project mapping**: apply user-controlled rules to classify activity, while
keeping the assumptions inspectable.
- **Reporting and export**: produce review-ready summaries and invoice-oriented
outputs without pretending classified time is automatically approved invoice
time.

This favors composability over one magic classifier. The point is not perfect
truth. The point is transparent, adjustable inference.

*[Hero image direction: see `docs/marketing/gittan-hero-image-spec.md`. The image should show local traces becoming classified candidates, with invoice-relevant time requiring human approval.]*

## The current beta blocker

The current blocker is not mainly runtime stability. The CLI works for my own
workflow, and the test suite is green.

The blocker is **time-to-useful-project-config**.

It is too much to ask a new user to hand-write every `timelog_projects.json`
rule before they see value. The next onboarding path needs to be guided:

1. run a local report,
2. show unexplained time,
3. show top domains with local timestamp hints,
4. suggest candidate project mappings,
5. require explicit approval before writing config.

That is the private beta I want to test: not whether Gittan can magically know
everything, but whether an evidence-first workflow can help a real person reach
a trustworthy first configuration quickly.

## What I am looking for

I am not looking for people who need hands-off invoice automation on day one.

I am looking for a few design partners: solo consultants, founders, and
AI-heavy developers who already feel the pain of reconstructing project time
from memory.

The question I want to test is:

**Can a local, evidence-first workflow help you trust your project-hour report
faster than screenshots, memory, or manual timers?**

If yes, there is something important here.

## Where this leaves me

Gittan is not a claim that time can be measured perfectly. It is a claim that we
can do better than memory plus guilt.

For technical teams, the lesson is broader than time tracking. When workflows
become AI-augmented and multi-context, trust comes from transparent pipelines,
explicit trade-offs, and reviewable outputs.

The future of work is not just faster output. It is better evidence for what
happened.

## A question for the DAIS community

If you had to reconstruct a high-stakes workweek tomorrow for billing,
compliance, or planning, which signal would you trust least: calendar, chat,
git history, browser traces, AI-agent logs, or memory?

## Links

- Site: [https://gittan.sh/](https://gittan.sh/)
- Code: [https://github.com/mbjorke/timelog-extract](https://github.com/mbjorke/timelog-extract)
