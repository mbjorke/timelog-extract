# Intent capture from inside the agent — an MCP surface

Status: **draft — spec only, nothing built**
Last updated: 2026-07-26
Owner: Maintainer + active agents

## Why the question has to move

`gittan intent` works, and it asks the right question. It asks it in the wrong
place: a terminal, later, about a conversation the operator has already left.
Recognition decays. The row says `2026-07-26 13:10 · 14 event(s) · session_01ab…`
and a title that may or may not mean anything by then.

The moment the answer is cheap and certain is *during* the conversation, and the
operator is already there — talking to the agent. So the question belongs where
the work is. `gittan intent` stays as the catch-up queue for everything that was
never asked live.

The dream, in the maintainer's words: being *asked* which customer a chat belongs
to, and having that answer stick.

## Why MCP rather than a Claude-specific hook

MCP is the one interface Claude Code, Claude Desktop, Cursor and a growing set of
other agents all speak. One stdio server, installed once, and every agent that can
reach it can ask the question. A Claude Code hook would work sooner but only there,
and this repo already collects from six IDE surfaces — a per-agent integration is
six integrations.

The server is local, stdio, no network, reading and writing the same
`~/.gittan/intent-capture.jsonl` that `gittan intent` already owns. It is a second
mouth on an existing store, not a new store.

## The hazard this spec exists to handle

**An LLM asked "which project is this?" will always produce an answer.** That is
the whole problem. If the agent answers on the operator's behalf, we have built a
confident guesser with a durable, authoritative log — *strictly worse than
`match_terms`*, because a `match_term` is at least a rule the operator wrote and
can read, while a fabricated intent record is indistinguishable from a decision.

The contract that makes intent worth having is that **an intent beats a
`match_term`** (confirmed by the maintainer, 2026-07-26,
`docs/task-prompts/session-intent-binding-task.md`). That contract is only
defensible while an intent means *a human decided*. An agent-authored record
inheriting that precedence silently voids it.

### Enforcement is impossible in-band — say so plainly

In a chat, every byte the human types reaches the tool through the agent. Nothing
the server receives can prove a human said it: an agent that wants to claim
`via: "mcp-human"` can. Any design premised on the server distinguishing them is
wishful.

So this spec does not try. It substitutes three properties that *are* achievable:

1. **A verbatim quote is required.** `answer_quote` stores the operator's own words
   as typed. It is not decoration — a fabricated binding now requires fabricating
   a quote, and a record whose quote does not read like a human answering a
   question is a visible tell on review. A record with an empty quote is not
   authoritative, full stop.
2. **Every agent-written binding is visible.** `gittan intent --list` marks its
   `via`, and a report whose rows moved shows `anchors.project_from = "intent"`.
   Nothing binds invisibly.
3. **Reversal is one append.** The log is append-only and latest-wins, so a wrong
   binding costs one correction and keeps its own history. Wrongness is cheap;
   silence is what would be expensive.

Auditability instead of enforcement. That is the honest trade, and it should be
stated in the tool description the agent actually reads — not just here.

## Tools

Three, deliberately: one to ask well, one to record, one to catch up.

### `gittan_list_projects` (read-only)

Returns the configured project names from `timelog_projects.json`.

Without this the agent invents plausible-looking names, and a binding to a project
that does not exist is a silent no-op at report time. The agent must offer the
operator real options, not guesses.

### `gittan_bind_session` (write)

```
session      string   the session key; omit to use the caller's own session
project      string   must match a configured project name
answer_quote string   REQUIRED — the operator's answer, verbatim
note         string   optional
```

Appends one record with `via: "mcp"`. Rejects an unknown project by name, listing
the known ones — the same failure mode `gittan intent --set` already handles.

The tool description must instruct: **ask the operator, then record what they
said.** Do not infer from the repo, the branch, the task, or the conversation. If
the operator has not answered in their own words, there is nothing to record.

### `gittan_pending_sessions` (read-only)

Unattributed sessions in a window, so an agent can raise the question unprompted
("three sessions from yesterday have no project — want to name them?"). This is
what turns intent capture from a thing the operator remembers to do into a thing
that gets offered.

## The open engineering question: what is the session key?

`session` is an anchor today, taken from `cliSessionId` in the Claude Code
transcript (`collectors/ai_logs.py:119`) and the cache-key session id for Desktop
Code. Both are derived by *reading files after the fact*. An MCP server is called
*during* the session and has no such privileged knowledge — the MCP protocol hands
a tool its arguments, not the host's session identity.

Three candidate resolutions, in order of confidence:

1. **The agent passes its own session id.** Claude Code knows it; whether it is
   exposed to an MCP tool call needs verifying against the current protocol and
   host behaviour before anything is built. **This is the load-bearing unknown of
   the whole spec** — verify it first, because the other two are worse.
2. **The server derives "the newest active session for this cwd"** from the same
   transcript files the collector already reads. No new dependency, and correct in
   the common case of one active session per directory. Ambiguous with two agents
   in one repo, which is not rare here.
3. **A hook writes the key, MCP only asks.** Claude Code hooks receive a
   `session_id` in their payload. If (1) fails, a hook can stamp the current
   session id somewhere the server reads — at the cost of being Claude-specific
   again, which is the thing MCP was chosen to avoid.

Resolve this before writing code. A spec that assumes (1) and discovers (2) has
built the wrong thing.

## Behavior

```gherkin
Feature: The intent question is asked where the work happens
  An operator names the customer during the conversation, not in a terminal later.

  Scenario: The agent asks and records the answer
    Given an agent with the gittan MCP server available
    And a configured project "Customer X"
    When the operator says the work belongs to Customer X
    Then a record is appended with via "mcp"
    And the record stores the operator's answer verbatim
    And a report attributes that session's hours to Customer X

  Scenario: The agent offers real options, not invented ones
    When the agent asks which project a session belongs to
    Then the choices come from the configured project list
    And an unknown project name is rejected with the known names listed

  Scenario: A binding with no human answer is not authoritative
    Given an agent calls the bind tool with an empty answer_quote
    Then the record is not treated as a decision
    And it does not outrank a match_term

  Scenario: Agent-written bindings are visible as such
    Given a session bound through the MCP surface
    When the operator lists bindings
    Then the record shows it came from an agent surface
    And the report row records that its project came from an intent

  Scenario: Correcting an agent's binding costs one append
    Given a session bound to the wrong project through MCP
    When the operator binds it again
    Then both records remain in the log
    And the later one wins

  Scenario: Unattributed sessions can be raised unprompted
    Given two sessions from yesterday with no project
    When the agent queries pending sessions
    Then both are returned with their titles and times
```

## What this does not do

- **No new store.** Same `~/.gittan/intent-capture.jsonl`, same record contract,
  same latest-wins semantics. `gittan intent` and this surface are two doors into
  one log.
- **No inference.** The server never classifies. If it did, it would be
  `classify_project` with worse inputs and a durable log.
- **No network, no daemon, no auth.** Local stdio only. The write-path
  authentication question in `intent-capture.md` § *Open questions* stays open for
  bookmarklets and gateways; a stdio server run by the operator's own agent
  sidesteps it entirely.
- **Not a replacement for `gittan intent`.** Sessions nobody asked about live —
  mobile chats, anything captured from another device — still need the queue.
- **No browser-chat coverage.** That needs the `url_hash` key, still unbuilt.

## Cost of being wrong

Worth stating, because it is what makes this buildable at all: a wrong intent
record misattributes hours on an invoice. That is not a crash, it is a billing
error the operator may not catch, which is why every mitigation above is about
*visibility* rather than correctness. The reason this is acceptable is that the
status quo — `Uncategorized`, or a `match_term` that spills onto every future
event containing that string — is also wrong, just less legibly.

## Open questions

- The session key (above). Blocking.
- Should `gittan_bind_session` refuse when the operator's answer is absent, or
  record it as a *suggestion* that the review queue promotes? Refusing is simpler
  and keeps the log clean; suggesting captures agent context that is genuinely
  useful. Recommend refusing until there is evidence the suggestion path is
  wanted — a queue of unconfirmed guesses is a second backlog.
- Distribution. An MCP server needs installing; `pip install timelog-extract`
  already puts the code on disk, so this may be one documented config block rather
  than a package. Decide before writing install docs.
- Does the same surface eventually answer *"is this billable?"* — the other
  question only the operator can answer? Out of scope here, same shape.

## Traceability

- story_id: pending
- covers: intent
- spec_status: draft
- implementation_status: not started
- created_at: 2026-07-26
- last_updated_at: 2026-07-26
- implementation.pr: none
- implementation.branch: none
- validation.evidence: none — spec only
- validation.decision: pending
- changelog:
  - 2026-07-26: Drafted after the session-keyed binding shipped, on the
    maintainer's question of whether the intent question can move into Claude and
    eventually all agents. Records the agent-authored-answer hazard and the
    session-key unknown as the two things to resolve before building.

## Related

- `docs/specs/intent-capture.md` — the record contract this consumes.
- `docs/task-prompts/session-intent-binding-task.md` — the shipped session-keyed
  half, and the two maintainer decisions this inherits.
- `core/intent_store.py` — the store both surfaces write to.
- `docs/specs/timestamp-standard.md` — `captured_at` is a durable record, so §1.
