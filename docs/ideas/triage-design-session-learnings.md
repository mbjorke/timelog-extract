# Triage UX design session — learnings and restart preconditions

Status: exploratory / paused (2026-06); restart blocked on grounding docs below

## What happened

A Claude.ai design session for the triage review UX (project prompts +
five sequenced design prompts: information architecture → interaction
model → AI suggestion layer → edge cases → component spec) drifted wrong
in the first iteration. The mockups assumed **rich signals that do not
exist**: thread titles ("Refactor triage state machine"), message counts,
clean session links to IDE events.

What Gittan actually sees for the hardest triage cases:

```text
source: claude.ai   detail: https://claude.ai/chat/<opaque-id>   ~41m   adjacent: none
source: chrome      detail: app.example-builder.test             ?      adjacent: none
source: cursor      detail: src/api.ts                           22m
```

No semantic content. The design solved a world where the signal problem
is already solved — which is precisely the problem **intent capture**
(`../specs/intent-capture.md`) exists to fix. With intent capture, triage
becomes *confirmation* of mostly-classified events instead of
*archaeology* over opaque ones.

## Learnings worth keeping

1. **User intention is the missing layer** — the central insight of the
   whole planning arc. No triage UX, however good, compensates for signals
   this weak. Capture intent at the moment of work; review confirms it.
2. **Triage presupposes project config.** You cannot review
   classifications with nothing to classify against. Setup (bootstrap →
   match_terms → tracked_urls → audit) is strictly upstream; the design
   must encode this prerequisite chain, including the first-run case
   (200 unclassified events, no config yet).
3. **Design prompts must embed real signal examples.** Any designer —
   human or AI — invents plausible-but-fictional data otherwise.

## Preconditions before restarting the design session

Two grounding documents, both requiring a machine with real local data:

- **A. Real signal examples** — anonymized actual `--format json` /
  `review --json` output showing what `claude.ai`, `chrome`, and `cursor`
  events look like, and what high vs low confidence means in practice.
  (Follow AGENTS.md fixture hygiene: neutral placeholders, no real
  customer/project identifiers.)
- **B. Setup → triage prerequisite chain** — how the current
  semi-automatic `gittan setup` flow works and where triage begins.
  Largely assembleable from `docs/ideas/fast-project-mapping-playbook.md`
  and `docs/product/cli-command-map.md`.

The five-prompt session structure itself held up and can be reused once
Prompt 0 (project instructions) embeds both documents.

## Related

- `../specs/intent-capture.md` — the fix for the weak-signal root cause
- `../ideas/conversational-ui-stack.md` — where triage sits relative to
  the modal wall (it is the canonical web-view case)
- `../ideas/fast-project-mapping-playbook.md` — existing manual workflow
  the UX must improve on
