# Pedagogical Demo Script

Goal: show clear value in 3 minutes with a stable flow:
`setup -> config -> TIMELOG before/after commit -> status -> report (Last 7 days interactive)`

## Ultra-short 60s Script

### Commands

```bash
export DEMO_HOME="$HOME/.gittan-demo-live"; export GITTAN_HOME="$DEMO_HOME"; unset GITTAN_PROJECTS_CONFIG
mkdir -p "$DEMO_HOME/stage-repo" && cd "$DEMO_HOME/stage-repo" && git init -q
git config user.name "Demo User" && git config user.email "demo@example.com"
rm -f timelog_projects.json TIMELOG.md && test ! -f timelog_projects.json && test ! -f TIMELOG.md && echo "EMPTY_START_OK"
gittan setup --interactive
printf "demo-%s\n" "$(date +%s)" > demo-proof.txt && git add demo-proof.txt && git commit -m "feat: prepare invoice narrative baseline"
sed -n '1,40p' TIMELOG.md
gittan status --last-week --additive
gittan report
```

Select: `Last 7 days` in the interactive report prompt.

### Word-for-word talk track (about 60s)

"I start from a completely empty state so this is reproducible. Setup creates the initial project profile with no hidden manual steps. I then make one commit, and that commit is automatically written into TIMELOG with timestamp and subject. This gives immediate traceability from development activity to reporting evidence. Status gives the fast weekly overview, and report provides the detailed evidence layer. So in under a minute, we go from empty state to audit-friendly time evidence."

## 3-minute Script

### 0) Opening line (10s)

"I start from a completely empty state, set up in under a minute, make one commit, and show how that immediately becomes traceable in worklog and report output."

### 1) Empty start + setup (45s)

```bash
export DEMO_HOME="$HOME/.gittan-demo-live"
export GITTAN_HOME="$DEMO_HOME"
unset GITTAN_PROJECTS_CONFIG
mkdir -p "$DEMO_HOME/stage-repo"
cd "$DEMO_HOME/stage-repo"
git init -q
rm -f timelog_projects.json TIMELOG.md
test ! -f timelog_projects.json && test ! -f TIMELOG.md && echo "EMPTY_START_OK"
gittan setup --interactive
```

Talk track:
- "You can see we start from a truly empty state."
- "Setup guides me step-by-step without remembering flags."

### 2) Show config quality (20s)

```bash
sed -n '1,80p' timelog_projects.json
```

Talk track:
- "This config is the classification foundation."
- "Good profiles here mean cleaner reports later."

### 3) TIMELOG before/after commit proof (60s)

```bash
echo "--- TIMELOG BEFORE ---"
test -f TIMELOG.md && sed -n '1,40p' TIMELOG.md || echo "(missing)"

git config user.name "Demo User"
git config user.email "demo@example.com"
printf "demo-%s\n" "$(date +%s)" > demo-proof.txt
git add demo-proof.txt
git commit -m "feat: prepare invoice narrative baseline"

echo "--- TIMELOG AFTER ---"
sed -n '1,80p' TIMELOG.md
```

Talk track:
- "Before commit: empty or missing."
- "After commit: timestamped entry appears automatically."
- "Commit title is useful baseline for invoice narratives."

### 4) Status (25s)

```bash
gittan status --last-week --additive
```

Talk track:
- "Status is the fast cockpit: hours and sessions."

### 5) Report interactive (20s)

```bash
gittan report
```

Select: `Last 7 days`.

Talk track:
- "Report gives traceable evidence behind the totals."

### 6) Closing line (10s)

"The key value is a clean start, fast setup, automatic commit-to-worklog logging, and report-ready evidence in minutes."

## Fallback lines

- If TIMELOG does not update:
  - "Good catch. The hook triggers on real commits, so I will make one new unique commit now."
- If output looks sparse:
  - "This is a clean demo profile. The point here is flow and traceability."
- If classification looks noisy:
  - "Classification is tuned iteratively in project profiles; the core evidence flow is already reliable."
