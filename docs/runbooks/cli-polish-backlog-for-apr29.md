# CLI Polish Backlog for Apr 29

Purpose: preserve today's UX insights and turn them into a minimal, low-risk polish plan before the live demo.

Latest status update (2026-04-20):

- Lovable delivered strongly today; overall progress is slightly ahead of plan.
- Install path is still pending: `brew install gittan`.
- Demo app + design-system handoff is done: https://gittan.lovable.app/handoff
- Sales funnel fed by design system is live (not interactive yet): https://gittan-sales.lovable.app/
- Substack update must be sent before tomorrow and should include today's new progress.
- Product/domain naming direction:
  - `gittan-sales` -> `gittan.sh`
  - real app -> `app.gittan.sh`
  - `gittan.html` in this repo -> retire

Scope rule:

- Prioritize clarity over novelty.
- Max 3-5 polish changes before Apr 29.
- No deep refactors or behavioral rewrites.

---

## Decision Questions (answer before coding)

1. For `jira-sync` candidate display, should branch-derived keys be:
   - hidden when commit-derived keys exist for the same day, or
   - shown but visually de-emphasized with a clear warning?
2. Should `jira-sync` summary tail hints be:
   - always printed, or
   - printed only on non-perfect outcomes (failed/skipped/unresolved)?
3. For setup simplification, is the preferred near-term approach:
   - introduce a new explicit `--advanced` flag, or
   - keep current flags and only reduce default line density now?
4. For Apr 29 scope, do we lock to:
   - `P0` only, or
   - `P0 + tiny P1.2 copy polish` if tests remain green?

Record decisions here before implementation:

- Q1: **Hide** branch-derived candidates for a day when commit-derived candidates exist for that day (implemented in `core/cli_jira_sync.py`; keeps one clear path in dry-run output).
- Q2: **Always** print one `Next:` line after the summary (including successful posts and empty runs).
- Q3: **Deferred** — no `--advanced` for `setup` in this batch; reduce default density later if needed.
- Q4: **P0 only** for this pass; P1.2 copy polish only if tests stay green and time allows.

---

## Priority 0 (must-have)

### P0.0 Close install path before demo messaging

Problem observed:

- CLI install story is still not closed in the preferred production wording.

Desired UX:

- Public install instruction is `brew install gittan`.

Acceptance criteria:

- Install path validates cleanly on a fresh environment.
- Docs and demo copy consistently use Homebrew install flow.

Validation:

```bash
brew install gittan
gittan -V
```

---

### P0.1 Reduce Jira key noise in `jira-sync` candidate output

Problem observed:

- Branch-derived key (`GIT-123`) appears alongside valid commit-derived keys (`KAN-1`), creating demo noise.

Desired UX:

- Prefer commit-derived keys in display and optionally de-emphasize or suppress branch fallback when commit keys exist for the same day.

Acceptance criteria:

- Demo run shows one clear valid candidate path.
- Summary remains truthful (`posted/skipped/failed` accounting unchanged).

Validation:

```bash
python3 timelog_extract.py jira-sync --today --dry-run --jira-sync on --git-repo .
python3 -m unittest tests/test_jira_sync.py
```

---

### P0.2 Add explicit one-line "what happened next" in `jira-sync`

Problem observed:

- After summary output, users may not know immediate next action for fail/skip states.

Desired UX:

- Print a single next-step hint based on outcome:
  - fail auth/permission -> "verify credentials and issue visibility"
  - posted>0 -> "verify worklog in Jira issue"
  - unresolved>0 -> "add issue keys in commits/branch"

Acceptance criteria:

- One concise tail line appears in all outcome paths.
- No extra verbose block by default.

Validation:

```bash
python3 timelog_extract.py jira-sync --today --dry-run --jira-sync on --git-repo .
python3 -m unittest tests/test_jira_sync.py
```

---

## Priority 1 (should-have)

### P1.1 Setup output: keep default concise, move diagnostics to advanced mode

Problem observed:

- Setup is strong but still visually dense for first-time users.

Desired UX:

- Default (`setup`, `setup --dry-run`) remains concise.
- Advanced details behind explicit flag (e.g. future `--advanced`/verbose mode).

Acceptance criteria:

- First screen and summary remain readable in <20 seconds.
- Existing safe behavior and dry-run semantics unchanged.

Validation:

```bash
python3 timelog_extract.py setup --dry-run
bash scripts/cli_impact_smoke.sh
```

---

### P1.2 Report/status consistency polish

Problem observed:

- Core commands are good, but we should tighten consistent "next step" and wording tone.

Desired UX:

- Ensure `report` and `status` close with aligned guidance language.

Acceptance criteria:

- Tone and final hint lines are consistent.
- No regression in command outputs.

Validation:

```bash
python3 timelog_extract.py report --today --source-summary --quiet
python3 timelog_extract.py status --today
python3 -m unittest tests/test_cli_regression_smoke.py
```

---

## Priority 2 (nice-to-have, only if time)

### P2.1 Gap analysis messaging marker

Problem observed:

- Gap analysis runs but needs stronger real-data confidence to support external narrative.

Desired UX:

- Reach approximately 98% screen-time explanation on real data, or clearly document the remaining gap causes and mitigation plan.
- Keep "internal reconciliation artifact" labeling until confidence is consistently high.

Acceptance criteria:

- No ambiguity about whether this is stage-demo surface.
- Reconciliation confidence is quantifiable and easy to explain.

Validation:

```bash
python3 scripts/run_screen_time_gap_analysis.py
```

---

## Proposed execution order

1. `P0.1` Jira key noise
2. `P0.2` Jira next-step line
3. `P1.1` Setup concise/advanced split (if tiny)
4. `P1.2` Report/status tone alignment
5. `P2.1` Gap-analysis messaging (only if time)

---

## Focused Branch + Commit Plan (for fast first CodeRabbit review)

Branch:

- `task/cli-polish-p0-jira-sync`

Commit plan:

1. `test(jira-sync): cover branch/commit key display and summary outcomes`
   - touch only `tests/test_jira_sync.py` (and tiny fixture helpers if needed)
2. `ux(jira-sync): reduce key-noise and add one-line next-step hints`
   - touch only `core/cli_jira_sync.py` and minimal helper logic
3. `docs(runbook): capture final behavior and demo-safe wording`
   - touch only this runbook + any directly linked docs

Pre-review command gate:

```bash
bash scripts/cli_impact_smoke.sh
python3 -m unittest tests/test_jira_sync.py tests/test_cli_regression_smoke.py
```

PR strategy:
- Open PR right after commit 1+2 (docs can be follow-up if needed).
- Request first CodeRabbit review early; keep later changes incremental and small.

---

## Next Focus: Gap Analysis on Real Data (after CLI polish PR is open)

Goal:
- Validate gap analysis with your own real dataset and target ~98% of screen-time explained before broad demo positioning.

Execution:

```bash
python3 scripts/run_screen_time_gap_analysis.py
python3 scripts/calibration/run_screen_time_gap_analysis.py
```

Review checklist:
- Is the markdown output readable to a non-author in under 30 seconds?
- Are top deltas explained with obvious next actions?
- Is terminology consistent with stage wording ("estimate", "reconciliation", "local-first")?
- Is explained screen-time percentage clearly reported and trending toward 98%?

If output is hard to explain:
- capture 3 concrete friction points,
- convert each into one scoped change request,
- implement only the highest-impact wording/structure change before Apr 29.
- keep a visible tracker for "% explained" across reruns.

Status field for this cycle:
- Gap analysis: `INTERNAL_ONLY` -> `DEMO_READY` (target) or `KEEP_INTERNAL` (acceptable fallback).
- Screen-time explained: `<value>%` (target `98%`).

---

## Narrative and launch-surface alignment (new)

Before Apr 29, ensure all demo/release artifacts align on:

- marketing/sales surface: `gittan.sh`
- product app surface: `app.gittan.sh`
- legacy `gittan.html` retirement plan in this repo
- common docs shared between design system and funnel/app narrative
- Substack publication timing and content consistency with the above

Deferred note (this week, not blocking today):

- Align shared CLI + app documentation with Lovable handoff package: https://gittan.lovable.app/handoff
- Produce one canonical “common docs” handover artifact for:
  - collectors/source model
  - installation/onboarding flow
  - naming and route map (`gittan.sh` / `app.gittan.sh`)
  - demo-safe vs internal-only surfaces

---

## Guardrails before each polish commit

Run:

```bash
bash scripts/cli_impact_smoke.sh
python3 -m unittest tests/test_cli_regression_smoke.py tests/test_jira_sync.py
```

If command behavior changes materially:

- update runbook/docs in same commit,
- keep commit scope single-purpose.

