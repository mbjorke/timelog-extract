# Stage demo — speaker notes (Gittan)

**Audience:** Large room · **Tone:** Same as root `[README.md](../../README.md)` — clear, confident, not salesy.

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
For now, we also have a temporary demo page at **[https://gittan-sales.lovable.app/](https://gittan-sales.lovable.app/)**.

## Demo flow (3 minutes: onboarding focus)

1. **Frame the pain**
  - "Most tools show monolithic blocks like 'Terminal 4h'."
  - "That is not enough when someone asks what happened and why the hours are real."
2. **Show setup-first workflow**
  - Prove empty start (`EMPTY_START_OK`) so audience sees no hidden seed data.
  - Use canonical demo seeds: `Akturo (pdc)`, `Sundblom (blueberry)`, `Gittan (blueberry)`, plus other `blueberry-*` projects.
  - Run `gittan setup` and highlight project/customer bootstrap.
  - Open `timelog_projects.json` and show quality from scratch (projects, customers, match terms).
  - Show `TIMELOG.md` presence in demo home to anchor local-first evidence.
  - Make one commit in a demo repo and show the new appended `TIMELOG.md` entry.
  - Call out why it matters: commit/PR title is a practical baseline for invoice narrative.
  - Run `gittan status` for quick snapshot.
  - Run `gittan report`, then select `Last 7 days` in the interactive timeframe prompt.
3. **Close with outcome**
  - "Less memory reconstruction, more auditable reporting."
  - "Observed -> classified -> approved, with human approval as the gate."

## One-liner installs (show on slide or terminal)

```bash
pipx install timelog-extract && gittan -V
```

Optional (if your Homebrew tap is live):

```bash
brew tap <your-github>/gittan && brew install gittan && gittan -V
```

Details: `[docs/runbooks/homebrew-tap.md](../runbooks/homebrew-tap.md)`.

## Live demo commands (safe defaults)

```bash
export DEMO_HOME="${DEMO_HOME:-$HOME/.gittan-demo-clean}"
export GITTAN_HOME="$DEMO_HOME"
test ! -f "$DEMO_HOME/timelog_projects.json" && test ! -f "$DEMO_HOME/TIMELOG.md" && echo "EMPTY_START_OK"
gittan setup
python3 - <<PY
import json
import os
from pathlib import Path
p = Path(os.environ["DEMO_HOME"]).expanduser() / "timelog_projects.json"
d = json.loads(p.read_text(encoding="utf-8"))
print("projects:", len(d.get("projects", [])))
print("worklog:", d.get("worklog"))
PY
ls -la "$DEMO_HOME"
mkdir -p "$DEMO_HOME/commit-proof-repo" && cd "$DEMO_HOME/commit-proof-repo"
git init && git config user.name "Demo User" && git config user.email "demo@example.com"
printf "demo\n" > README.md && git add README.md && git commit -m "feat: demo PR title baseline"
cat TIMELOG.md
gittan status
gittan report
```

Optional export example:

```bash
gittan report --today --format json
```

## If something breaks on stage

- Say: *"I will switch to the stable path: quick snapshot first, then full weekly report."*
- Run `gittan status`, then `gittan report` and choose `Last 7 days`.
- Say: *"The numbers can vary, but the flow is fixed: setup context, status, then reviewable report."*

## Closing line

If this resonates, read the DAIS draft and try the CLI on your own workflow:

- Site: [https://gittan.sh/](https://gittan.sh/)
- Temporary demo page: [https://gittan-sales.lovable.app/](https://gittan-sales.lovable.app/)
- Repo: [https://github.com/mbjorke/timelog-extract](https://github.com/mbjorke/timelog-extract)
