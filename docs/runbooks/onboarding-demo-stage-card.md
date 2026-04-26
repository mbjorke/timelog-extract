# Onboarding demo stage card

Status: active quick card

Use this during live demos. For full reset/setup details, see
`docs/runbooks/repeatable-onboarding-demo.md`.

## 3-minute version

Opening line (0:00-0:20):

- "Most of us can ship faster with AI, but we still need accountable hours."
- "Gittan turns local traces into reviewable project-hour evidence."
- "Only what you approve becomes invoice truth."

Command flow and fixed narration:

1. `0:20-0:30` prove empty start (`EMPTY_START_OK`)
2. `0:30-1:20` `gittan setup`
3. `1:20-1:40` show `timelog_projects.json` quality
4. `1:40-1:55` show `TIMELOG.md`
5. `1:55-2:15` one commit in demo repo, then show appended `TIMELOG.md` line
6. `2:15-2:30` `gittan status`
7. `2:30-2:45` `gittan report` (select `Last 7 days` in prompt)
8. `2:45-3:00` close

What to point out:

- `setup seed names`: "Akturo (pdc), Sundblom (blueberry), Gittan (blueberry), plus blueberry-*."
- `setup`: "In under a minute we create a usable project/customer baseline."
- `EMPTY_START_OK`: "This always starts from zero, no preloaded config."
- `timelog_projects.json`: "This is from scratch and high quality: real projects, real customers, useful match terms."
- `TIMELOG.md`: "This is the local worklog anchor in the same demo environment."
- `commit + TIMELOG.md`: "Each commit appends a timestamped line; commit/PR title is invoice-narrative seed."
- `status`: "Quick snapshot before deeper output."
- `report`: "Select Last 7 days interactively, then show full weekly evidence output."

Closing line (2:45-3:00):

- "Less memory reconstruction, more accountable hours."
- "Observed -> classified -> approved, with human approval as the gate."

## 5-minute version

Opening line (30s):

- "AI output is fast; accountability still needs a human."
- "Gittan keeps evidence local-first and reviewable."

Command flow:

1. `gittan setup`
2. `gittan doctor`
3. `gittan report --today --source-summary`
4. `gittan triage`

What to point out:

- `setup`: first-run bootstrap lowers time-to-useful-config.
- `doctor`: confirms source posture before claims.
- `report`: candidate hours are evidence, not auto-invoice.
- `triage`: guides unexplained gaps; user stays in control.

Closing line (15s):

- "Observed -> classified -> approved. Approval is always human."

## If something breaks on stage

Fallback sequence:

1. Run `gittan status`
2. Run `gittan report` and select `Last 7 days`
3. Say: "The key point is the evidence chain: setup context, quick snapshot, then full report."
4. Say: "Setup details are documented; this is the stable demo path."

Do not improvise risky commands in live demos.

## Pre-demo one-liner reminder

- Reset and isolation workflow: `docs/runbooks/repeatable-onboarding-demo.md`