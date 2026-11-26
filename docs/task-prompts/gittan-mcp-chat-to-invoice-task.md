# Gittan MCP — chat from hours to invoice basis (product owner)

Planning artifact. No feature code. Produced by a `gittan-product-owner` pass on
2026-11-26, on the maintainer's question: *users need a way to chat with their
favorite assistant about producing invoicing material — should an MCP server go
next, and does it belong in this repo?*

## Traceability

- story_id: `pending`
- promote: yes (`next`)
- story_id.note: no issue by design — per the `gittan-product-owner` issue-lifecycle
  rule, the issue is opened by whoever starts M-0
- spec_status: `draft`
- implementation_status: `not built`
- created_at: `2026-11-26`
- last_updated_at: `2026-11-26`
- implementation.pr: `pending`
- implementation.branch: `pending`
- implementation.commits: `[]`
- validation.evidence: `pending`
- validation.decision: `conditional GO` — for M-0 only; M-1..M-4 wait on M-0's answer
- changelog:
  - `2026-11-26: Initial pass. Answers "MCP next?" with next (not now), places it in this repo as a gittan mcp entry point, and extends the intent-capture MCP draft with the approval and invoice-basis tools.`

---

## The answer

**Priority: `next`.** Not `now`: the current `now` work (the hours → approved
basis → invoice demo flow) uses the CLI and does not need a protocol layer.
**Start condition:** building may begin as soon as the current `now` items are
done. It is not tied to a calendar month, so if they finish early, M-0 starts
early.

**Home: this repo.** A `gittan mcp` stdio entry point (module under `core/`),
shipped in the same `pip install timelog-extract`. It is a thin adapter over
`core/engine_api.py`, `core/intent_store.py` and `core/reported_time.py`. A
separate repo would duplicate version coupling to the truth payload for no gain.
A separate repo only becomes the right call for a *hosted* server, which is
`do not build yet` (below).

## Why the earlier "no MCP" stance now has its trigger

`docs/ideas/conversational-ui-stack.md` and `docs/product/external-integrations.md`
(Phase 1) say: the CLI is the API; an agent with terminal access plus a skill doc
needs no MCP; *revisit when a concrete consumer demands it*.

That stays true for terminal agents (Claude Code, Cursor, Codex): they can
already go from hours to an invoice basis with `gittan report --format json` and
`gittan reported review`. The consumer that cannot is the **chat-only assistant**
(Claude Desktop, ChatGPT and similar) used by freelancers who never open a
terminal. Distribution through an accounting tool brings exactly those users.
That is the concrete consumer the earlier docs were waiting for.

## The chat-to-invoice shape

Two servers, composed by the user's assistant. Gittan never talks to the
accounting tool.

```
assistant ──stdio──► gittan mcp (local, no network)
   │                   hours, pending sessions, bind, approve, invoice basis
   │
   └──────────────► accounting tool's own MCP (e.g. NoCFO's public MCP)
                       creates a DRAFT invoice from the basis rows
```

- Gittan's server holds **no accounting credentials**. Private-first holds: local
  stdio, reads and writes only `~/.gittan` (or `GITTAN_HOME`).
- The invoice basis is **confirmed/edited `reported_time` only**. Observed time
  never reaches an invoice without a human confirmation.
- The accounting step creates a **draft**. Accepting and sending stay with the
  human in the accounting tool.
- The CLI path (a `gittan <tool>-invoice` command calling the accounting API
  directly) stays the terminal-user path. The MCP path does not replace it.

## Decision filter (`docs/product/gittan-vision.md`)

| Question | Answer |
| --- | --- |
| Improves trusted reporting quality? | Yes, if approval stays human (M-3) and the session key resolves (M-0); intent asked live beats intent asked later |
| Reduces admin burden? | Yes: hours → basis → draft without a terminal |
| Local-first, cloud/agent access optional, explicit, minimal? | Yes: local stdio; the user chooses to install it; no network |
| Preserves consent and privacy? | Yes: no credentials, no upload; the assistant only sees what the user's own agent asks for |
| In scope, or just technically possible? | In scope once a chat-only consumer exists; that is why it is `next`, not `now` |

## Backlog

### M-0 — Resolve the blockers (`now` once started, ~1 h, no feature code)

The two open questions from `docs/specs/intent-capture-agent-surface.md`:

1. **Session key.** Can an MCP tool call learn the host's session id (Claude Code,
   Claude Desktop, Cursor)? Record the answer per host, with evidence. Pick
   resolution 1, 2 or 3 from that spec.
2. **Distribution.** One documented config block vs an optional extra
   (`timelog-extract[mcp]`) for the MCP SDK dependency. Decide before writing
   install docs.

Acceptance criteria:
- A short decision note in `docs/decisions/` with the per-host session-key result
  and the chosen distribution.
- This spec's `validation.decision` updated to `GO` or `NO-GO` for M-1..M-4.

### M-1 — Read-only server (`next`)

Tools: `gittan_list_projects`, `gittan_pending_sessions` (both as in the intent
spec), and `gittan_report` (period → per-project/per-day hours from
`engine_api.run_report_payload`, summarized; never raw event detail by default).

### M-2 — Bind a session to a customer (`next`)

`gittan_bind_session` exactly as specified in
`docs/specs/intent-capture-agent-surface.md`: verbatim `answer_quote` required,
`via: "mcp"`, append-only, latest wins.

### M-3 — Approve hours (`next`)

- `gittan_reported_proposals` (read): the same proposals `gittan reported review`
  builds, for a period.
- `gittan_reported_confirm` (write): confirm, edit or dismiss one proposal. Same
  rule as bind: requires the operator's verbatim `answer_quote`; the record shows
  it came from an agent surface; reversal is one more append.

### M-4 — Invoice basis (`next`)

`gittan_invoice_basis` (read-only): confirmed/edited `reported_time` for one
customer and period, shaped as invoice rows (description, date, quantity in
hours, project). This is the handoff the assistant passes to the accounting
tool's MCP. No network, no prices (prices live in the accounting tool).

### Later

- MCP prompts that walk the "Friday close" flow (pending → bind → approve → basis).
- "Is this billable?" as a second operator-only question (same shape as bind).

### Do not build yet

- **Hosted or remote Gittan MCP.** Needs auth and moves data off the machine;
  conflicts with `decisions/private-not-local.md`.
- **Gittan MCP calling an accounting API.** Duplicates the accounting tool's own
  MCP and puts credentials in Gittan's server.
- **Agent-authored approval** (confirm without an operator quote). It turns a
  billing decision into a guess with an authoritative log.

## Behavior

```gherkin
Feature: Chat from hours to an invoice basis

  Scenario: Only approved hours reach the invoice basis
    Given observed hours for "Customer X" this week
    And none of them are confirmed
    When the assistant asks Gittan for the invoice basis for "Customer X"
    Then the basis is empty
    And the reply says the hours need approval first

  Scenario: The operator approves in chat
    Given a proposal of 3.5 hours for "Customer X" on Friday
    When the operator says "yes, 3.5 h is right"
    And the assistant confirms the proposal with that quote
    Then a confirmed reported_time record is appended with via "mcp"
    And the record stores the operator's answer verbatim

  Scenario: Confirming without the operator's words is refused
    When the assistant calls the confirm tool with an empty answer_quote
    Then nothing is written
    And the error says the operator must answer in their own words

  Scenario: Gittan does not talk to the accounting tool
    Given the Gittan MCP server is running
    When any Gittan tool is called
    Then no network request is made

  Scenario: The basis is ready for an accounting draft
    Given 12 confirmed hours for "Customer X" in November
    When the assistant asks for the November basis for "Customer X"
    Then it receives one row per project and day with hours as the quantity
    And the rows carry no prices
```

## Risks

- **Session key unknown (M-0).** If no host exposes it, bind falls back to
  "newest active session for this cwd", which is ambiguous with two agents in one
  repo.
- **Assistant fabricates quotes.** Not preventable in-band (see the intent spec).
  Mitigation is visibility: `via: "mcp"` on every record, and a review list.
- **Maintainer time.** M-1..M-4 compete with distribution work; keep slices small
  enough to ship one per week.

## Related

- `docs/specs/intent-capture-agent-surface.md` — the MCP draft this extends (M-1, M-2).
- `docs/ideas/conversational-ui-stack.md` — the "no MCP until a consumer demands it" stance.
- `docs/product/external-integrations.md` — Phase 1 / Phase 2 integration shape.
- `docs/task-prompts/reported-time-layer-task.md` — the approval layer M-3/M-4 read.
- `core/engine_api.py`, `core/intent_store.py`, `core/reported_time.py`.
