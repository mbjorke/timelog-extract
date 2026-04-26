# Asciinema Expected-Outcome Loop

Status: active workflow

## Purpose

Make demo-critical and walkthrough-critical feature flows verifiable before push.

This is the default workflow for future features that rely on terminal UX quality.

## Required loop

1. Define the expected observable outcome up front.
2. Record a clean run with `asciinema rec`.
3. Replay with `asciinema play`.
4. Compare output with the expected outcome checklist.
5. Fix mismatches and rerun until the expected result is clearly visible.

Do not mark the feature flow "ready" if expected output is missing, ambiguous, or
only partially visible.

## Expected-outcome checklist template

Use this template per feature flow:

- Context/setup is explicit (paths/env/range).
- One clear "before" state is shown.
- One clear "after" state is shown.
- The key value signal is visible without interpretation gymnastics.
- No blocking errors, broken prompts, or hidden manual steps.

## Minimal command pattern

```bash
export DEMO_HOME="${DEMO_HOME:-$HOME/.gittan-demo-clean}"
mkdir -p "$DEMO_HOME/recordings"
asciinema rec "$DEMO_HOME/recordings/<feature>-$(date +%Y%m%d-%H%M%S).cast"
# run the feature flow
exit
asciinema play "$DEMO_HOME/recordings/<feature-file>.cast"
```

## Evidence in PR/agent output

For each feature flow validated with this loop, include:

- expected result summary (1-3 bullets)
- observed result summary (1-3 bullets)
- mismatch/fix summary (if any)
- cast path used for verification

