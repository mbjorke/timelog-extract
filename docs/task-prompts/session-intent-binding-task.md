# Session intent binding — answer once, about one conversation

A chat carries no repo, no working directory and no URL worth matching. Measured
2026-07-26 (`docs/evals/claude-surface-attribution-measurement.md`): a desktop
chat produces honest hours and lands on `Uncategorized` unless the operator
happened to type the project name in the prose.

The only way to fix that today was to add a `match_term`. But a term is not an
answer about *this* conversation — it is a rule that matches every future event
containing that text. A one-off decision became permanent classification noise.
That is the patching this task removes.

**The operator's framing:** the dream is being *asked* which customer a chat
belongs to, and having that answer stick.

## What was missing

Three pieces existed; one did not.

| Piece | State before |
|---|---|
| A queue of undecided rows | `gittan review` already surfaces them |
| A stable per-conversation id | both collectors held one internally |
| A record shape for a decision | `docs/specs/intent-capture.md`, draft, unconsumed |
| **A place to put the answer** | **missing** — `core/config.py` accepts only `match_terms` and `tracked_urls` |

The session id never reached an event: the anchor kinds in use were `repo`, `dir`,
`branch`, `label`. So even with a queue and a record shape, there was no key to
bind a decision to.

## Behavior

```gherkin
Feature: A session is attributed by decision, not by pattern
  A chat with no repo and no URL can still land on the right customer.

  Scenario: An unattributed session is offered for a decision
    Given a captured chat session with hours and no project
    When the operator runs gittan intent
    Then the session is listed with its title, time and turn count
    And answering with a project binds that session

  Scenario: The binding survives into the report
    Given a session bound to "Customer X"
    When the report is generated
    Then those hours appear under "Customer X"
    And no match_term was added to the projects config

  Scenario: A decision outranks a text match
    Given a session whose text matched another project
    And the operator bound it to "Customer X"
    Then the report shows "Customer X"
    And the row records that its project came from an intent

  Scenario: Re-deciding appends rather than edits
    Given a session already bound to "Customer X"
    When the operator binds it to "Customer Y"
    Then both records remain in the log
    And the later one wins

  Scenario: Only unattributed sessions are asked about
    Given one session already attributed by its repo anchor
    And one session with no anchor at all
    When the queue is built
    Then only the unanchored session is offered
```

## Design decisions

**The key is the session, not the text.** `session` is now an anchor kind, taken
from `cli_id` (Claude Code) and the cache-key session id (Desktop Code) — both
already in hand, no new parsing. One key names one conversation and nothing else,
so a decision cannot spill.

**Keys are case-folded on both sides.** `make_event` lowercases every anchor value
except `label` (`core/events.py::_normalize_anchor_value`), so a session anchor in
a report is already lower case while a raw id from a cache key is not. Found by a
failing end-to-end test rather than by reading: the binding silently matched
nothing. `normalize_key` now folds on write and on lookup, so an id copied from
anywhere binds the same session.

**An intent beats a match_term.** A deliberate answer outranks a heuristic
pattern; otherwise a stale rule could silently override the answer and asking
would be pointless. **Overrulable** — invert it if you would rather have config
win.

**One binding per session.** A session spanning two projects is a real case, but
splitting by time span is a different feature. Bound whole, and said so.

**Re-projection is auditable.** An overridden row carries
`anchors.project_from = "intent"` and `anchors.project_before_intent`, so "why is
this Customer X?" answers *"because you said so"* rather than *"because a term
happened to hit"*.

**Applied after replay, not inside `classify_project`.** The classifier stays
untouched — one override pass over events at a single point in
`core/report_service.py`, so the blast radius on the number engine is one line and
restored evidence is bound too.

## Surfaces

- `gittan intent` — walks the window's unattributed sessions and asks.
- `gittan intent --set SESSION=PROJECT` (repeatable, `--note`) — non-interactive.
- `gittan intent --list` — current bindings with date and provenance.
- Log: `~/.gittan/intent-capture.jsonl`, append-only, inside the data repo that
  `gittan_data_autocommit.sh` already commits.

## Known limits

- **Only sessions that were captured can be asked about.** The Claude mobile app
  still writes no local artifact, so there is no session to bind. Unchanged by
  this task.
- **Browser chats are not covered yet.** `key_kind: "url"` is accepted by the
  store but nothing produces a URL key; that is the `url_hash` half of
  `intent-capture.md`, still unbuilt.
- **Plain desktop chat is still not a capture source**, so its sessions do not
  reach the queue. One `CAPTURE_SOURCES` entry away whenever those hours are
  judged better in the queue than absent.

## Traceability

- story_id: `GH-465`
- covers: intent
- spec_status: approved
- implementation_status: built
- created_at: 2026-07-26
- last_updated_at: 2026-07-26
- implementation.pr: pending
- implementation.branch: claude/tavlan-stammer-over-u55fn6
- implementation.commits: []
- validation.evidence: `tests/test_intent_store.py` (23 tests incl. an end-to-end
  report assertion that bound hours move off `Uncategorized`, and that a decision
  overrides a text match); live demo — a desktop-code session's 0.4h moved from
  `Uncategorized` to a named customer after one binding, with no config change
- validation.decision: GO
- changelog:
  - 2026-07-26: `session` anchor in both Claude collectors, `core/intent_store.py`
    (append-only log, latest-wins, auditable re-projection), the override wired
    into the report path, and `gittan intent` as the question surface.
