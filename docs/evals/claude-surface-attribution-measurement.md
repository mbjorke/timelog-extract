# Claude surfaces — how much attribution signal each one carries

Date: 2026-07-26
Mode: synthetic fixtures through the real collectors and `classify_project`
Question: can a chat surface stand in for a Claude Code session as billable
evidence — and does capturing more surfaces reduce the `match_terms` /
`tracked_urls` burden?

Prompted by the operator's question: if sessions leave transcripts, do we get
project attribution for free and escape the brittle term/URL matching?

## Setup

One 8-turn work session, fabricated five ways. The prose is held constant in two
variants, because that turns out to be the whole story:

- **names the project:** "Let's fix the thinning in timelog-extract's chrome collector"
- **does not:** "Let's fix the thinning in the browser history collector"

Real chat usually looks like the second — you discuss the work, not the slug.
Profile `match_terms`: `["timelog-extract", "gittan"]`.

## Result

| Surface | Structural anchor available | Project, prose *without* the name | Hours |
|---|---|---|---|
| Claude Code, `cwd` in a real clone | git remote slug + dir | **gittan** | 0.58h |
| Claude Code, `cwd` not a repo | dir only | Uncategorized | 0.58h |
| Desktop **Code**, git session metadata | repo slug + label + dir | **gittan** | 0.58h |
| Desktop **Code**, no git metadata | dir + label | Uncategorized | 0.58h |
| Desktop **chat** (`local-agent-mode-sessions`) | none | Uncategorized | 0.58h |
| Desktop chat, prose *names* the project | none | gittan | 0.58h |

The slug signal was isolated separately: a neutral session-directory name with
`cwd` pointing at a real clone still classifies (`resolve_path_repo_slug` →
`mbjorke/timelog-extract`, anchors `dir, repo`), while the same neutral directory
with a non-repo `cwd` does not. So attribution there comes from the **remote
slug**, not from a path that happens to contain the project name.

## What it means

**Hours are never the problem.** Every surface that leaves a local transcript
recovers the same 0.58h span. The `min_session` floor and the session math do
their job identically whether the source is Claude Code or a plain chat.

**Attribution splits cleanly on whether a structural anchor exists.** Not on how
much text there is:

- **Claude Code** and **Desktop Code mode** both carry a repo identity —
  `cwd` → remote slug for the former, `session_context.outcomes[].git_info.repo`
  for the latter. Desktop Code's is *worktree-invariant by construction*: in the
  fixture `cwd` was deliberately a sandbox path (`sandbox/worktree`) and it still
  attributed correctly from session metadata.
- **Desktop plain chat** has no anchor at all. `collect_claude_desktop`
  classifies on the message detail alone, so the project lands only if you
  happened to type its name. That is worse than a `tracked_urls` entry in one
  respect: a URL mapping is deterministic, whereas this depends on your phrasing
  that day.

**So capture does not reduce the term/URL burden — it moves the burden to where
an anchor exists.** For code-shaped work the awkwardness is already solved and
not by `match_terms`: the repo slug is structural. For chat-shaped work no amount
of capturing creates an anchor that was never recorded.

## Answer to the original question

**Desktop Code mode can stand in** for a Claude Code session as evidence: same
hours, and a worktree-invariant repo anchor plus a human session title for the
timeline label.

**Desktop plain chat cannot.** It yields honest hours attached to
`Uncategorized`, which lands the work in the review queue rather than on an
invoice line — the exact manual mapping the operator wanted to escape.

And neither covers the **mobile app**, which writes nothing to any device the
operator controls. That gap is not an attribution problem but an artifact
problem, and it stays with `docs/specs/intent-capture.md`.

## Next step — taken 2026-07-26

`desktop-code` is now in `CAPTURE_SOURCES` (`core/session_capture.py`) — one
registry entry, no new parsing, with `tests/test_capture_desktop_code.py` pinning
that the metadata repo slug still attributes correctly after capture even when
`cwd` is a sandbox path. `gittan capture --source` selects a subset.

Plain `desktop` chat is still out. It is one more registry entry whenever the
`Uncategorized` hours are judged better in the review queue than absent — that is
a product call, not a technical one.

Not proposed: mining chat text for project identity. That is a different
decision from reading timestamps — see `#354`'s display-vs-identity rule and
`docs/specs/source-evidence-policy.md`.

## Reproducibility

Fabricated fixtures only; no real chat content, no local data. The Claude Desktop
cache entries reuse the builders in `tests/test_claude_desktop_events.py`
(`_make_entry`), and the Claude Code transcripts are plain JSONL. The one real
input is this repository's own git remote, used to show that
`resolve_path_repo_slug` resolves where a synthetic path cannot.
