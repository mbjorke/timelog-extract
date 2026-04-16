# Decision: Terminal UX reference from Copilot CLI

Status: Draft reference  
Date: 2026-04-16  
Owner: Maintainer + active agent

## Context

During a live local test of GitHub Copilot CLI, two onboarding/ready-state screens
showed a high-quality terminal UX pattern that maps well to `gittan` goals
(clarity, trust, and first-command momentum).

This note captures those patterns as reusable design guidance.

## Reference screens captured

### Screen A: Branded first-run + trust confirmation

- Branded hero block with version and short mission line.
- Low-noise onboarding text:
  - "Describe a task to get started."
  - "Tip: /help ..."
  - "Copilot uses AI. Check for mistakes."
- Explicit trust modal before folder access.
- Clear risk framing ("read files", "execute code", "unsafe if untrusted").
- Strong action labels with safe default decision flow.

### Screen B: Post-trust ready state

- Confirmation event line:
  - trusted folder was added.
- Environment summary line:
  - custom instructions count
  - MCP server count
  - skill count
- Prompt/status footer includes high-signal context:
  - cwd
  - git branch
  - PR reference
  - active model + effort level
  - remaining request budget indicator

## UX patterns to adopt in Gittan

1. **Branded start frame**
   - Keep a compact hero at start of interactive flows (`setup`, `doctor`,
     future web terminal).
   - Show version and a single actionable first sentence.

2. **Trust and safety gate language**
   - For any operation reading local sources, explain capabilities in plain
     language before consent prompts.
   - Use explicit "safe vs risky" wording, not implicit jargon.

3. **Environment readiness snapshot**
   - After setup/init, show one-line summary of loaded context, for example:
     configured sources, active profile, optional integrations.

4. **High-signal statusline**
   - Keep command prompt context visible and short:
     repo/branch/timeframe/source strategy.
   - Preserve low visual noise while improving orientation.

5. **Persistent help affordance**
   - Keep one visible hint for command discovery (`/help` or equivalent).

## Immediate implementation targets

- `gittan setup`: add a compact branded intro + explicit local-data safety note.
- `gittan doctor`: add a clearer "what will be checked" preface and
  post-check environment summary.
- `gittan.sh` live terminal demo: copy the two-phase pattern:
  - trust/safety context first
  - then concise ready-state context panel.

## Non-goals

- Pixel-perfect visual cloning of Copilot CLI.
- Introducing heavy animation or decorative UI noise.

## Decision

Use this Copilot CLI flow as a **pattern reference**, not a strict template.
Prioritize:

- trust clarity,
- first-action clarity,
- compact readiness context.
