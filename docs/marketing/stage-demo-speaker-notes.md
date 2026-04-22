# Stage demo — speaker notes (Gittan)

**Audience:** Large room · **Tone:** Same as root [`README.md`](../../README.md) — clear, confident, not salesy.

## Opening (45-60 seconds)

We all like to believe someone has full control of AI systems. In practice, no single person fully controls system-level behavior. The real question is not control, it is trust.

**Gittan** exists for that reason. It turns local traces you already leave behind (IDE, browser, mail, commits, worklog) into reviewable project-hour reports, without shipping your raw day to a cloud by default.

The idea is simple: if we cannot inspect every internal reasoning step, we can still make the output chain auditable.

## Three-sentence version (if time is tight)

Gittan aggregates local work signals into honest, review-ready hours. It is local-first by design: you choose sources, you keep the files, and you export JSON or PDF only when needed. This demo shows how to move from AI-era chaos to a defensible chain of evidence.

## Keynote script (90 seconds)

Most of us like to believe someone fully controls AI systems.  
In practice, no single person fully controls system-level behavior.

So the real question is not control.  
The real question is trust.

That is why I built **Gittan**.

Gittan is a local-first CLI that turns the traces you already leave behind (IDE activity, browser context, commits, worklogs) into reviewable project-hour reports.

The shift is simple but important:  
from "I think this is what I worked on"  
to "Here is an auditable chain of evidence."

In the AI era, output speed is exploding. People with basic programming experience can build complex systems faster than ever.  
That is powerful, but it also means accountability matters more than ever.

Gittan is not about surveillance.  
It is about reconstructing reality under pressure, without sending your raw day to a cloud by default.

So if you have ever reached Friday and asked, "What did I actually do this week?"  
this is for you.

Less memory reconstruction.  
More defensible reporting.  
Not perfect truth, but accountable evidence.

If you want to try it:  
**gittan.sh**  
For now, we also have a temporary demo page at **https://gittan-sales.lovable.app/**.

## Demo flow (3-5 minutes)

1. **Frame the pain**
   - "Most tools show monolithic blocks like 'Terminal 4h'."
   - "That is not enough when someone asks what happened and why the hours are real."
2. **Show the workflow**
   - Run install/version check.
   - Mention local-first posture and optional sources.
   - Show a report command and source summary.
3. **Close with outcome**
   - "Less memory reconstruction, more auditable reporting."
   - "Not perfect truth, but accountable evidence."

## One-liner installs (show on slide or terminal)

```bash
pipx install timelog-extract && gittan -V
```

Optional (if your Homebrew tap is live):

```bash
brew tap <your-github>/gittan && brew install gittan && gittan -V
```

Details: [`docs/runbooks/homebrew-tap.md`](../runbooks/homebrew-tap.md).

## Live demo commands (safe defaults)

```bash
gittan doctor
gittan report --today --source-summary
```

Optional export example:

```bash
gittan report --today --format json
```

## If something breaks on stage

- Fall back to **PyPI + pipx** — always matches what’s published.  
- Say: *“Full setup and collectors are in the repo README and `gittan doctor`.”*

## Closing line

If this resonates, read the DAIS draft and try the CLI on your own workflow:

- Site: [https://gittan.sh/](https://gittan.sh/)
- Temporary demo page: [https://gittan-sales.lovable.app/](https://gittan-sales.lovable.app/)
- Repo: [https://github.com/mbjorke/timelog-extract](https://github.com/mbjorke/timelog-extract)
