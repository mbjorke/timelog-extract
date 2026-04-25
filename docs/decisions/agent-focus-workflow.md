# Agent Focus Workflow

Status: active guidance

## Purpose

Use a lightweight GSD-inspired workflow to keep agent work focused without
turning this repository into a heavy project-management system.

The goal is not to install or mirror GSD. The goal is to preserve the useful
principles: declare intent, plan only enough, execute in a clean scope, verify
with evidence, and leave the next action obvious.

## When to Use

Use this workflow when work is ambiguous, spans multiple files, touches release
or agent rules, or starts from an idea rather than a specific edit.

For tiny edits, follow `AGENTS.md` fast-path directly.

## Workflow

1. **Discuss / frame**
   - State the intended outcome in one or two sentences.
   - Name what is out of scope for this pass.
   - If the current tree is dirty, group changes by intent before editing.

2. **Plan**
   - Write 3-7 concrete checklist items.
   - Prefer an existing `docs/task-prompts/` spec for larger work.
   - Stop and split if the checklist contains unrelated intents.

3. **Execute**
   - Work on a short-lived `task/*` branch from current `main`.
   - Keep the diff aligned with one intent.
   - Do not mix feature code, docs reorg, and follow-up cleanup unless the user
     explicitly asks for a combined sweep.

4. **Verify**
   - Run the smallest relevant test or smoke check first.
   - Run `bash scripts/run_autotests.sh` before calling push-ready work done.
   - For CLI-facing changes, also run `bash scripts/cli_impact_smoke.sh`.

5. **Ship / hand off**
   - Summarize outcome, validation evidence, and remaining risk.
   - Leave one explicit next action: continue, review, PR-ready, or split.

## Escalation Rule

Stop coding and reframe when any of these happen:

- More than three unrelated change clusters appear in `git status`.
- A task branch has been merged or deleted while local work continues.
- The implementation starts solving a different product question than the one
  stated in the framing step.
- Validation requires a larger behavioral decision than the current task owns.

## Relationship to Existing Rules

This workflow complements `AGENTS.md`, the task prompt traceability rules, the
daily repo hygiene routine, and the pre-push quality gate. If there is a
conflict, the stricter safety or validation rule wins.
