# Repeatable onboarding demo runbook

Status: active runbook

## Purpose

Run the same onboarding demo repeatedly (10+ times) with predictable results,
without damaging your real local config.

This runbook focuses on local CLI onboarding (`gittan setup`, `status`, `report`)
plus explicit `TIMELOG.md` visibility in a recording-friendly flow.

## Demo goal

Show a clean first-run path:

1. start with no projects config,
2. run setup and create a high-quality `timelog_projects.json`,
3. show setup -> TIMELOG.md -> status -> report flow,
4. optionally restore previous local state.

## Canonical demo environment

Use an isolated demo home:

- `DEMO_HOME="$HOME/.gittan-demo-clean"`
- `GITTAN_HOME=$DEMO_HOME`
- unset `GITTAN_PROJECTS_CONFIG`

This keeps your normal config untouched.

## Preflight (before each recording)

From repo root (`timelog-extract`):

```bash
export DEMO_HOME="$HOME/.gittan-demo-clean"
mkdir -p "$DEMO_HOME"

# Use home-based config resolution for this session
export GITTAN_HOME="$DEMO_HOME"
unset GITTAN_PROJECTS_CONFIG

# If your demo binary is named gittan-dev locally:
alias gittan='gittan-dev'
```

Verify active config target:

```bash
python3 - <<'PY'
from core.config import resolve_projects_config_path_and_source
p,s = resolve_projects_config_path_and_source()
print(p)
print(s)
PY
```

Expected source:

- `auto_profile_home` (or `GITTAN_HOME`)

## Hard reset to true scratch state

This is mandatory for every demo take.

Run before each new take:

```bash
rm -f "$DEMO_HOME/timelog_projects.json" "$DEMO_HOME/TIMELOG.md"
```

Optional proof of empty start:

```bash
ls -la "$DEMO_HOME"
```

Expected:

- no `timelog_projects.json`
- no `TIMELOG.md`

Hard gate (must pass before you continue):

```bash
test ! -f "$DEMO_HOME/timelog_projects.json" && test ! -f "$DEMO_HOME/TIMELOG.md" && echo "EMPTY_START_OK"
```

## Demo flow (no special flags)

Use this order on stage/recording:

1. verify `EMPTY_START_OK`
2. `gittan setup`
3. open and show `timelog_projects.json` quality
4. show `TIMELOG.md`
5. make one demo commit in isolated demo repo
6. show updated `TIMELOG.md` content
7. `gittan status`
8. `gittan report`
9. in interactive prompt for timeframe, select `Last 7 days`

Canonical demo seed set (use these names in setup prompts):

- `Akturo` -> customer `pdc`
- `Sundblom` -> customer `blueberry`
- `Gittan` -> customer `blueberry`
- include other `blueberry-*` projects under customer `blueberry`

High-quality config check (show this right after setup):

```bash
python3 - <<PY
import json
import os
from pathlib import Path
p = Path(os.environ["DEMO_HOME"]).expanduser() / "timelog_projects.json"
d = json.loads(p.read_text(encoding="utf-8"))
projects = d.get("projects", [])
print(f"config: {p}")
print(f"projects: {len(projects)}")
missing = [x.get("name","<unnamed>") for x in projects if not x.get("customer")]
print(f"missing customer: {len(missing)}")
print("worklog:", d.get("worklog", "<missing>"))
PY
```

Quality bar to say out loud:

- at least 3 relevant projects are present,
- each has a meaningful customer value,
- `match_terms` include repo/domain cues (not only generic words),
- `worklog` points to local `TIMELOG.md`.

To show `TIMELOG.md` clearly in terminal:

```bash
ls -la "$DEMO_HOME"
[ -f "$DEMO_HOME/TIMELOG.md" ] && echo "TIMELOG.md present" || echo "TIMELOG.md not present yet"
```

If `TIMELOG.md` is not present yet and you want to show first creation:

```bash
printf "## %s\n- Demo: created clean worklog\n" "$(date '+%Y-%m-%d %H:%M')" > "$DEMO_HOME/TIMELOG.md"
ls -la "$DEMO_HOME"
```

Commit-proof step (shows automatic timelog append on commit):

```bash
mkdir -p "$DEMO_HOME/commit-proof-repo"
cd "$DEMO_HOME/commit-proof-repo"
git init
git config user.name "Demo User"
git config user.email "demo@example.com"
printf "demo\n" > README.md
git add README.md
git commit -m "feat: demo PR title baseline"
cat TIMELOG.md
```

What to say while showing `TIMELOG.md`:

- "This line is auto-appended on commit, with real timestamp and commit title."
- "Commit/PR title becomes a strong baseline for invoice narrative and review."

## What to verify in output

- `setup` creates `timelog_projects.json` and shows onboarding summary.
- `timelog_projects.json` is validated for quality, not only existence.
- `TIMELOG.md` visibility is explicit (present/created in demo home).
- one commit appends a new `TIMELOG.md` entry automatically.
- `status` gives a quick snapshot.
- `report` is run without flags and timeframe is selected interactively as `Last 7 days`.

## Between-take reset (fast)

To run another take from scratch:

```bash
rm -f "$DEMO_HOME/timelog_projects.json" "$DEMO_HOME/TIMELOG.md"
```

Then repeat demo flow.

## Recording with asciinema

`asciinema` is installed and works well for repeated dry-runs.

Optional helper (paste once per shell session):

```bash
demo_rec() {
  export DEMO_HOME="${DEMO_HOME:-$HOME/.gittan-demo-clean}"
  mkdir -p "$DEMO_HOME/recordings"
  rm -f "$DEMO_HOME/timelog_projects.json" "$DEMO_HOME/TIMELOG.md"
  asciinema rec "$DEMO_HOME/recordings/onboarding-$(date +%Y%m%d-%H%M%S).cast"
}
```

Then start a fresh take with:

```bash
demo_rec
```

Start recording after preflight + hard reset:

```bash
mkdir -p "$DEMO_HOME/recordings"
asciinema rec "$DEMO_HOME/recordings/onboarding-$(date +%Y%m%d-%H%M%S).cast"
```

During recording:

- run the standard flow (`setup` -> `TIMELOG.md` -> commit proof -> `status` -> `report`) and choose `Last 7 days` interactively
- keep pauses short and read output headings out loud

Stop recording:

- press `Ctrl+D` (or type `exit`)

Quick local replay:

```bash
asciinema play "$DEMO_HOME/recordings/<file>.cast"
```

## Lightweight recording review checklist

After each take, check:

- first 10 seconds clearly show clean start conditions.
- `setup` includes project/customer bootstrap interaction.
- `TIMELOG.md` is visibly present (or visibly created) in the demo home.
- commit-proof step clearly shows a fresh appended entry in `TIMELOG.md`.
- `status` and `report` outputs are readable without scrolling chaos.
- timeframe selection in `report` is done interactively (`Last 7 days`), not via flags.
- no accidental local path confusion (wrong `GITTAN_HOME`).
- closing line lands after evidence output, not before.

## Live fallback lines (verbatim)

If `setup` gets stuck or too long:

- "I will switch to the stable path now: setup context, then quick snapshot, then full report."
- Optional quick proof: "One commit creates one auditable timelog line."
- Run `gittan status`
- Run `gittan report` and select `Last 7 days` in the prompt

If output differs from expected:

- "The exact numbers can vary, but the flow is fixed: observed first, then classified, then human approval."
- "What matters in this demo is the accountable evidence chain."

## Optional backup/restore of existing home config

If you demo against a personal Gittan home instead of `DEMO_HOME`, backup first:

```bash
cp "$HOME/.gittan-home/timelog_projects.json" "$HOME/.gittan-home/timelog_projects.pre-demo-$(date +%Y%m%d-%H%M%S).json"
```

Restore later by copying that backup back to
`$HOME/.gittan-home/timelog_projects.json`.

## Troubleshooting

- `No such command 'gittan'`:
  - verify alias or PATH (`alias gittan='gittan-dev'` for local demos).
- Config path confusion:
  - rerun `resolve_projects_config_path_and_source()` check.
- Unexpected existing data:
  - verify `GITTAN_HOME` and remove files in `$DEMO_HOME`.
- Demo drift from expected output:
  - reset scratch state and rerun from step 1.

## Post-demo cleanup

To return terminal to normal behavior:

```bash
unalias gittan 2>/dev/null || true
unset GITTAN_HOME
unset GITTAN_PROJECTS_CONFIG
unset DEMO_HOME
```

