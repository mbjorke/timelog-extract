# Project-field detection — signal survey and binding design

How Gittan decides which project an event belongs to today, which signals each
source already carries, and the cheapest deterministic changes that would raise
auto-detection — with the Grok "Project" (Swedish UI: *Projekt*) case as the
worked example.

## Traceability

- story_id: `pending` (investigation; file issues from §6)
- spec_status: `draft`
- implementation_status: `not built` (survey only — no code changed)
- created_at: `2026-08-25`
- last_updated_at: `2026-08-26`
- implementation.pr: pending
- implementation.branch: `claude/project-field-detection-1txdx2`
- implementation.commits: []
- validation.evidence: code references in §1–§3 (read at commit `fca62c4`)
- validation.decision: `pending`
- changelog:
  - `2026-08-25: Initial survey; findings F1–F7, recommendation R1–R3.`
  - `2026-08-26: Added §9 vocabulary alignment (source note kept in private gittan-home) and §10 idea bank I1–I9.`
  - `2026-08-26: Added §11 reconciliation against the documented matching order in docs/product/agent-context.md; Q5 reclassified as defect D1.`

## Scope and anti-goals

In scope: deterministic, local, debuggable signals. Explicit anti-goals, carried
from `docs/specs/intent-capture-agent-surface.md`:

- No LLM classifying chat *content* into projects as the primary path.
- No SaaS sync of raw chats.
- No dependency on undocumented Grok-app internals.

---

## 1. The current detection chain

```
timelog_projects.json
  └─ core/config.py::load_profiles → normalize_profile()      # field normalization
core/report_service.py::run_timelog_report
  └─ resolve_attribution_classify_fn(...)                     # v1 = match_terms
      └─ core/report_service.py::_classify_project
          └─ core/domain.py::classify_project(text, profiles, "Uncategorized")
  └─ core/report_runtime.py::collect_runtime_events
      └─ core/pipeline.py::collect_all_events
          └─ collectors/*.py  — each builds its own haystack, calls classify_project
  ── post-passes, in this order ───────────────────────────────
  1. core/evidence_store.py::maybe_replay
  2. core/device_labels.py::ensure_live_device
  3. core/intent_store.py::apply_intents        # human decision beats match_terms
  4. core/derived_attribution.py::apply_derived_attribution   # git remote only
  └─ core/report_aggregate.py::aggregate_report
```

### 1.1 How `match_terms` actually match

`core/domain.py::classify_project` (index built once per profile list by
`_compile_profiles_index`, cached in `_get_compiled_index`):

- **Case:** haystack is lowercased by the caller path (`text.lower()`); terms are
  lowercased at index time. Matching is case-insensitive throughout.
- **Word boundary:** a purely alphanumeric term (`gittan`) must match a whole word
  — it is looked up in a `frozenset` of `\w+` tokens, so `cat` never matches
  `category`. A term containing `-`, `.`, `/`, or a space (`customer-b.test`,
  `example project`) is matched as a **plain substring** anywhere.
- **URL normalization:** only Lovable's host quirk is normalized
  (`_normalize_lovable_url_token`, e.g. `*.lovableproject` → `*.lovableproject.com`).
  No general URL canonicalization exists in the matcher.
- **Term sources indexed:** `match_terms`, the profile `name`, and `tracked_urls`.
  Nothing else.

### 1.2 Weights and conflict resolution

| Impact | What produces it | Score | Counts as "specific" |
| --- | --- | --- | --- |
| `_IMPACT_URL` | a `tracked_urls` entry found in the text | 2.0 | yes |
| `_IMPACT_PATH` | a term containing `/` or `\` | 2.0 | yes |
| `_IMPACT_NORMAL` | an ordinary `match_terms` entry | 1.0 | yes |
| `_IMPACT_NAME` | the profile `name` | 1.0 | yes |
| `_IMPACT_GENERIC` | a term in `GENERIC_TOOL_TERMS` (jira, toggl, cloudflare…) | 0.25 | no (counted as generic) |

Winner = max of the tuple
`(score_sum, specific_hits, total_matched_term_length, -generic_hits, match_count)`,
with a floor of `specifics > 0 or score >= 1.0`; ties keep the earlier profile.

Two consequences worth naming:

- **Score is a sum, not a max.** Three ordinary terms (3.0) outrank one
  `tracked_urls` hit (2.0). "Most specific evidence wins" is *not* the current
  rule; "most evidence wins" is. There is no explicit priority or override field.
- **Longest-match is only a tiebreaker** (third element), not the primary rule.

### 1.3 How `tracked_urls` connect

Three different mechanisms, and they do not agree:

1. **In the matcher** — indexed as a 2.0-weight substring term
   (`core/domain.py:_compile_profiles_index`). Any collector whose haystack
   contains the URL benefits.
2. **`collectors/chrome.py::collect_claude_ai_urls`** — builds `url_map` from
   `tracked_urls` containing `claude.ai`, queries Chrome History for those URLs
   only, and picks the project with `next(... if tracked_url in url)` — **first
   configured profile wins, not the most specific URL.**
3. **`collectors/chrome.py::collect_gemini_web_urls`** — same shape, but does
   **longest-match** (`best_len`). Same problem, opposite rule.

Guardrails: `core/tracked_url_policy.py` rejects over-broad entries on
multi-tenant hosts (`claude.ai`, `chatgpt.com`, `gemini.google.com` bare or with
a generic route segment), surfaced by `core/projects_lint.py`.

### 1.4 Post-passes that beat `match_terms`

- **Intent** (`core/intent_store.py`): append-only JSONL at
  `~/.gittan/intent-capture.jsonl`, keyed `(key_kind, key)`, latest wins. Only
  `key_kind: "session"` has a producer; `apply_intents` reads
  `anchors["session"]` and nothing else. An overridden event records
  `anchors.project_from = "intent"` and `anchors.project_before_intent`.
- **Derived attribution** (`core/derived_attribution.py`): `Uncategorized` events
  carrying an `anchors.repo` of shape `owner/repo` become a derived row. Git
  remotes only, by design — "a directory leaf, a branch name and a session title
  are not durable identities". Never persisted.

### 1.5 What happens when nothing matches

- Project becomes `Uncategorized`. **No log line is emitted at classification
  time** — there is no per-event "why" trace; provenance exists only as anchors
  on events that *were* re-projected (`project_from`).
- The event is filtered out of the report unless `--include-uncategorized`,
  *except* when `core/events.py::is_always_included_event` keeps it: Lovable
  desktop rows, and **any event carrying a non-empty `anchors.label`** (session
  title) — titles are explicitly treated as primary mapping surface for chat
  tools.
- Downstream surfaces: `core/uncategorized_review.py` clusters them,
  `core/projects_audit.py` counts signals (`host/repo/dir/branch/label`),
  `core/report_nudges.py` + `core/anchor_nudge.py` nudge, `gittan review` /
  `gittan map` / `gittan intent` resolve them.

---

## 2. Signals available per source

Anchor namespace in use: `repo`, `dir`, `branch`, `label` (session title),
`host`, plus `session`, `cwd`, `slug`, `project_from`, `project_workspace`,
`project` (see F6). `core/anchor_plan.py::KNOWN_ANCHOR_KINDS` only sanctions
`host/repo/dir/branch/label`; `branch` and `label` are **ephemeral** and must not
be auto-promoted to `match_terms` (GH-342).

| Source | Haystack passed to `classify_project` | Anchors emitted | Session id? | Title? |
| --- | --- | --- | --- | --- |
| Claude Code CLI (`collectors/ai_logs.py:209`) | `slug dir_name meta_title branch detail` | repo, dir, branch, label, **session** | yes | yes |
| Claude Desktop (Code) (`collectors/claude_desktop_events.py:256`) | `slug cwd title detail` | repo, dir, label, **session** | yes | yes |
| Codex IDE (`collectors/ai_logs.py:318`) | `thread_name` | label | id in detail only | yes |
| Gemini CLI (`collectors/ai_logs.py:270`) | `proj_name detail` | dir | no | project dir |
| Cursor composer/agent (`collectors/cursor_composer.py:364`) | **title first, workspace+git as fallback** | label, dir, branch, `project_from`, `project_workspace` | conversation id available | yes |
| Cursor logs (`collectors/cursor.py:258`) | `workspace_path line` | repo/dir | no | no |
| VS Code chat (`collectors/vscode_chat.py:110`) | folder + text | repo/dir | no | partial |
| Conductor (`collectors/conductor.py:256`) | message text | repo | no | no |
| Zed (`collectors/zed.py:104`) | message content | repo, **project** (regex junk, F6) | no | no |
| Chrome generic (`collectors/chrome.py:403`) | `url title` | label (GitHub tab lead only) | n/a | page title |
| **Claude.ai (web)** (`collectors/chrome.py:288`) | **none — `classify_project` never called** | none | n/a | title captured, then discarded |
| **Gemini (web)** (`collectors/chrome.py:334`) | **none — `classify_project` never called** | none | n/a | same |
| Apple Mail (`collectors/mail.py:119`) | `to_addr subject` | label | no | subject |
| GitHub (`collectors/github.py:206`) | repo/issue haystack | — | no | issue title |
| TIMELOG.md (`collectors/timelog.py:50`) | entry snippet, then fallback haystack | — | no | n/a |
| Calendar (`collectors/calendar.py:227`) | `cal_title summary` | label | no | event title |

### Findings

- **F1 — `aliases` never classify anything.** `normalize_profile` merges
  `aliases` (+ name + `canonical_project`), but `_compile_profiles_index` does
  not index them. They are only used for CLI project selection
  (`core/report_runtime.py:66`) and the global timelog hook
  (`core/global_timelog_hook_script.py:48`). *Mirroring a Grok Project name into
  `aliases` would have zero effect on detection.*
- **F2 — the two web-chat collectors discard the title.** `collect_claude_ai_urls`
  and `collect_gemini_web_urls` read `title` from Chrome History, put it in
  `detail`, and attribute purely from `tracked_urls`. The strongest available
  chat signal is thrown away, and no `label` anchor is set — so those rows also
  miss `is_always_included_event`.
- **F3 — an untracked chat is invisible, not `Uncategorized`.** `collect_chrome`
  hard-excludes `claude.ai` and `gemini.google.com` in *both* branches, and the
  dedicated collectors return `[]` when `url_map` is empty. For every other host
  (grok.com included) the generic collector pre-filters SQL by
  `match_terms + name` — a visit whose URL and title contain no configured term
  is never read. **This is the single biggest gap: unmapped chat work does not
  appear in the uncategorized queue at all, so review can never surface it.**
- **F4 — the intent binding covers only sessions Gittan can see an id for.**
  `SUPPORTED_KEY_KINDS = ("session", "url")` but nothing produces a `url` key,
  and `apply_intents` only inspects `anchors["session"]`. Browser chats — the
  exact Grok case — have no binding path today.
- **F5 — title-first attribution already exists and works.**
  `classify_composer_conversation` (#544) scores title and workspace as
  independent passes, prefers the title, and records the loser as
  `anchors.project_workspace` so `core/report_nudges.py::title_workspace_conflicts_for_report`
  can show the conflict. This is the precedent to reuse, not to reinvent.
- **F6 — the `project` anchor kind is already occupied by junk.**
  `collectors/zed.py::_extract_project_anchors` writes
  `anchors["project"]` from `re.search(r"\b([a-z][a-z0-9_-]*(?: [a-z][a-z0-9_-]*){0,2})\b", ...)`
  — i.e. the first one-to-three lowercase words of any message. A real
  "app-declared project" anchor must not land in that namespace until this is
  fixed or renamed.
- **F7 — minor: stale docstring.** `run_interactive_anchor_flow` still says
  "Each anchor value (working directory, git branch, or session title) becomes a
  match_term"; the GH-342 guardrail below it skips ephemeral kinds. The code is
  right, the docstring is not.

---

## 3. The Grok "Project" field

**What the app models.** Grok groups chats under a *Project* (a container with
its own instructions/files); each chat keeps a separate *title*. The two are
different fields, and the Project is the one that carries billing meaning.

**What Gittan can read locally, today: nothing.**

- No Grok collector exists (`grep -rn grok` over the repo: zero hits).
- The xAI inference API exposes model calls, not app Projects — and even if it
  did, a network call for attribution is outside local-first.
- Chrome History gives `(visit_time, url, title)` and nothing else. Whether the
  Project name appears there depends entirely on whether Grok puts it in the
  URL path or the tab title, which is **unverified and must be measured on the
  operator's own machine before any design is committed** (see §6, Q1).
- Until that measurement exists, the honest statement is: the Project field is
  **not** a locally observable signal. The chat *title* and the chat *URL* are.

**Is it the same pattern as Claude `tracked_urls`?** Structurally yes — one
stable per-conversation URL, mapped to a project. But that pattern has three
known weaknesses that Grok would inherit and amplify:

1. It requires the operator to paste a URL per chat (`tracked_urls` is
   per-conversation on multi-tenant hosts, enforced by
   `is_over_broad_tracked_url`).
2. A URL not yet added yields **no event at all** (F3), so the cost of forgetting
   is silent hour loss, not a visible grey row.
3. Grok has no dedicated collector, so a `tracked_urls` entry would only work via
   the generic Chrome path — which means the *keyword prefilter* must also hit.

So: reuse the pattern for the *binding*, but fix the observability gap first, or
the binding has nothing to bind to.

---

## 4. Signal → status → reliability → action

| Signal | Exists today? | Where | Reliability | Action |
| --- | --- | --- | --- | --- |
| `match_terms` substring/word match | yes | `core/domain.py` | high when terms are specific; degrades badly with generic terms | keep as core |
| Profile `name` as implicit term | yes | `normalize_profile` | medium — a name like `gittan` is a generic word | keep, but lint generic single-token names |
| `tracked_urls` (per chat) | yes | matcher + 2 Chrome collectors | **high** when configured; zero coverage when not | unify to longest-match (R2) |
| `aliases` | field exists, **not used for detection** | F1 | n/a | either index them or document them as CLI-only |
| Git remote `owner/repo` | yes | `derived_attribution` | **highest** — worktree-invariant | keep; nothing to add |
| Working dir leaf (`dir`) | yes | `path_attribution_anchor` | medium — collides across machines | keep as fallback only |
| Git branch | yes (anchor) | ephemeral, not a rule | low — per-feature, short-lived | keep out of `match_terms` (GH-342) |
| **Chat/session title (`label`)** | captured as anchor; used for classification only by Cursor (F5) and Codex | F2, F5 | **medium-high** — human-authored, stable per thread, but re-titled by the tool | **promote to a first-class binding key (R1)** |
| Session id (`session`) | yes, Claude Code / Claude Desktop only | `intent_store` | **highest** — exact, but invisible for web chats | extend producers, not the rule |
| Web host (`host`) | yes, as a `tracked_urls` suggestion | `projects_audit` | low alone — one host, many customers | keep as suggestion only |
| **App-declared Project (Grok/ChatGPT folders)** | **no** | — | unknown — unmeasured (§6 Q1) | measure before designing (R3 gate) |
| Chat *content* (LLM classification) | no | — | untrustworthy as primary | anti-goal — do not build |

---

## 5. Recommended minimal change (ranked, cheapest first)

### R1 — Bind by title, with the same store that already binds by session

**One new `key_kind`, no new config field, no new schema.**
`core/intent_store.py` already supports `(key_kind, key) → project`, latest-wins,
append-only, and already beats `match_terms`. Today `apply_intents` only reads
`anchors["session"]`. Change it to fall back to `anchors["label"]` under
`key_kind: "title"`:

```python
# core/intent_store.py::apply_intents  (sketch)
SUPPORTED_KEY_KINDS = ("session", "url", "title")
...
binding = (
    bindings.get(("session", session)) if session else None
) or (
    bindings.get(("title", normalize_key(anchors.get("label")))) if label else None
)
```

Why this and not a new config field:

- A title binding is **one answer about one thread**, not a rule that matches
  every future event containing that text — the exact distinction
  `core/intent_store.py` was built for. Putting "Defensible Hours for AI
  Developer Work" into `match_terms` would classify every future mention of those
  words; a title binding does not.
- It inherits provenance for free (`anchors.project_from = "intent"`), reversal
  in one append, and `gittan intent --list` visibility.
- Session precedence stays intact: exact id beats title, title beats
  `match_terms`.

Cost: ~20 lines in `intent_store.py`, one `--set-title` path in
`core/cli_intent.py`, tests in `tests/test_intent_store.py`.

### R2 — Make chat evidence observable before it is classified

Three small, independent fixes, all in `collectors/chrome.py`:

1. **Emit the title as a `label` anchor and run it through `classify_project`**
   in `collect_claude_ai_urls` / `collect_gemini_web_urls` (F2). Attribution
   order: `tracked_urls` → title → `Uncategorized`. This alone makes a mis-typed
   or re-issued chat URL recoverable instead of silent.
2. **Longest-match in `collect_claude_ai_urls`** (F1.3 / F2) so it agrees with
   the Gemini collector and with `_IMPACT_URL` semantics.
3. **A bounded "known chat hosts" pass** so unmapped chats become *visible grey
   rows* instead of nothing (F3): for an explicit allowlist of conversation hosts
   (`claude.ai`, `chatgpt.com`, `gemini.google.com`, `grok.com`, …), collect the
   visit regardless of the keyword prefilter, set `anchors.label` from the tab
   title, and let it land as `Uncategorized`. `is_always_included_event` already
   keeps labelled rows visible, so they arrive in `gittan review` with a title
   the operator can actually answer about.

R2.3 is what makes R1 usable: **a binding needs a row to bind to.** Without it,
Grok work stays invisible however good the matcher gets. Note it also widens
what Gittan reads from browser history — it must be behind the same consent /
`collector_status` contract as any source change
(`docs/specs/source-collector-contract.md`).

### R3 — Only then: an app-declared `project` signal

Gated on measuring what Grok actually exposes (§6 Q1). If — and only if — the
Project name reliably appears in the URL path or tab title, add it as a new
anchor kind (**not** `project`, which is occupied by F6 — propose
`app_project`), and let it be bindable through the same
`(key_kind, key) → project` store as R1. No new matcher weight, no new config
array.

### What *not* to add

- **`session_titles[]` on the profile.** It would be a second `match_terms` with
  the same failure mode: a permanent text rule written to answer a
  one-conversation question, plus a new writer on `timelog_projects.json` (which
  #406 guards against). The intent log already is the binding layer.
- **A `bindings[]` block in config.** Same objection — and it would fork truth
  between config and `intent-capture.jsonl`. If a durable binding is ever wanted
  in config, it should be a *compaction* of the intent log, not a parallel input.

---

## 6. Config-format sketch (only if R1/R3 prove insufficient)

The recommendation is that no config change is needed. Recorded here so the
alternative is on the table rather than re-derived later:

```jsonc
{
  "projects": [
    {
      "name": "gittan",
      "match_terms": ["timelog-extract", "mbjorke/timelog-extract"],
      "tracked_urls": ["https://claude.ai/chat/<id>"],
      // Proposed only if the intent log proves too ephemeral in practice:
      "bindings": [
        { "kind": "title",       "value": "Defensible Hours for AI Developer Work" },
        { "kind": "app_project", "value": "Gittan", "source_hint": "grok.com" },
        { "kind": "url",         "value": "https://grok.com/c/<id>" }
      ]
    }
  ]
}
```

Rules if it is ever built: exact-match only (never substring), always outranks
`match_terms`, never outranks a `session` intent, and one writer — `gittan
intent --promote` compacting the JSONL — so config and the log cannot disagree.

## 7. Future MCP surface (sketch only)

Already specified in `docs/specs/intent-capture-agent-surface.md` — do not design
a second one. The relevant point for this survey: its `gittan_bind_session` tool
writes the **same** `intent-capture.jsonl` that `gittan intent` owns, requires a
verbatim `answer_quote`, and marks `via`. R1 extends that surface for free — a
`bind_thread(project, title|url)` tool is the same call with a different
`key_kind`, not a new mechanism. The hazard named in that spec applies unchanged:
an agent asked "which project is this?" will always produce an answer, so the
binding is only authoritative while it carries a human's words.

## 8. Open questions and risks

- **Q1 (blocks R3) — what does Grok actually expose locally?** Measure on the
  operator's machine: does the Project name appear in the URL path, the tab
  title, or neither? Does a Grok desktop/Electron app write anything under
  `~/Library/Application Support/`? Until this is answered, treat the Project
  field as unavailable, not as pending.
- **Q2 — title stability.** Chat tools rename threads (auto-titling on first
  turn, later re-titling). A title binding keyed on a string that changes silently
  re-orphans the thread. Mitigation: bind on first sighting, and treat a changed
  title as a new unbound row rather than a moved one — visible, not silent.
  Related prior art: the whole label-provenance family in
  `docs/task-prompts/source-identity-blindspot-backlog-2026-07-10-task.md`.
- **Q3 — title collisions across customers.** "Weekly sync", "Bug fix". Exact
  match on a short generic title will mis-bind. Mitigation: reject binding a
  title below a length/entropy floor, mirroring `is_over_broad_tracked_url`.
- **Q4 — privacy of R2.3.** Collecting known chat hosts regardless of keyword
  match reads more browser history than today. It must respect the existing
  consent surface and `docs/decisions/private-not-local.md`; titles are already
  stored as anchors, so the delta is *which* rows, not *what* is retained.
- **Q5 — resolved, and reclassified.** The decision this asked for is on record
  in `docs/product/agent-context.md`: matching is a priority ladder, so
  `tracked_urls` / bindings must *dominate*, not merely outweigh. What was an
  open question is now **D1** in §11 — a defect against documented intent.
- **Risk — F6 blocks the obvious name.** Any `app_project` work must first deal
  with Zed writing arbitrary text into `anchors["project"]`.

---

## 9. Vocabulary alignment

Checked against the maintainer's vocabulary/direction note (aug 2026), which is
kept in the private `gittan-home` repo rather than here — it carries positioning
and third-party process notes that do not belong in a public repository. Its own
stated priority is *"viktigast att låsa: vokabulär"*. Where the locked
term and the code term disagree, the code is what an operator debugs — so the
drift is worth naming before more is built on top.

| Locked term | What the code calls it today | Drift | Action |
| --- | --- | --- | --- |
| **Binding** — "stabil koppling thread/url/title → projekt" | `intent` — `core/intent_store.py`, `~/.gittan/intent-capture.jsonl`, `gittan intent` | **direct collision**: the vocabulary's `Binding` *is* the intent record | Decide one: rename the store to `binding`, or define in the vocabulary that an intent record is the binding's storage form. Do it before R1 adds a second `key_kind`, not after. |
| **Ledger** — "din sammanhållna tidssanning (events → block → godkända rader)" | three layers, none named ledger: `core/evidence_store.py` (events), `core/report_aggregate.py` (block), `core/reported_time.py` (approved rows) | naming gap, not a design gap — the three layers *are* the ledger | Map the term onto the three modules in the vocabulary table; do not rename code. |
| **Propose → approve → post** | already implemented as `reported_time` states `proposed \| confirmed \| edited \| dismissed`, with `REPORTED_STATES = {confirmed, edited}` gating billability | **none — the model exists** | Reuse these state names for *attribution* proposals too (I3/I4) instead of inventing a parallel vocabulary. |
| **Evidence_id** — "stabilt id för idempotent post" | not present (`grep evidence_id` → 0 hits); `core/evidence_record.py` fingerprints exist | missing | See I6 — cheapest as a field on the binding log first. |
| **Enhetssfär / device sphere** | `core/device_labels.py`, `core/session_capture.py::device_name` — device *labels* exist, no sphere model | partial | Fine for now; the binding log is the first thing that needs to cross devices (I6). |
| **Pollen / Pollinerare / Butler** | absent from code | correct — these are pitch metaphors | Keep them out of identifiers. |
| **Cloud session** | not modelled | absent | No action; a Grok/web row is already just an event with a passive-context role. |

One substantive consequence: the direction note already rules on this
survey's core question — *"Grok **Project**-namn svagt ensamt; **chat title**
starkare; MCP skriver samma bindings"*. R1 and R3 match that ruling; §6's
`bindings[]` config block does not (it would fork truth away from the binding
log) and stays a documented non-choice.

---

## 10. Idea bank — further deterministic signals

Ranked by (value ÷ cost). Everything here is local, deterministic, and
debuggable; nothing classifies chat *content*.

### I1 — Key the binding on the thread id, show the title

Every chat host puts an immutable conversation id in the path: `claude.ai/chat/<id>`,
`chatgpt.com/c/<id>`, `grok.com/c/<id>`. Extract it once into an `anchors.thread`
value and bind on **that**; the title is display and first-guess only.

Solves Q2 outright: a re-titled thread keeps its binding, because the key never
changed. Also makes `tracked_urls` redundant for the chat case — a thread id is a
`tracked_urls` entry with the volatile parts already stripped, and it cannot be
over-broad the way `is_over_broad_tracked_url` guards against.

Cost: one URL→id extractor + one `key_kind: "thread"`. **Do this instead of R1's
title key where an id exists; keep the title key for surfaces that expose no id
(Codex thread names, Cursor conversation titles).**

### I2 — Issue keys as a classification signal (Jira → Gittan, the prioritized direction)

`core/jira_sync.py` already has `extract_issue_key()` (`[A-Z][A-Z0-9_]+-\d+`) and
`build_issue_key_map(profiles)` — but they only serve *worklog posting*. Nothing
classifies on an issue key.

An issue key is the single highest-precision deterministic token in the whole
system: it is unique, human-authored, and it already appears in branch names,
commit subjects, PR titles and chat titles ("GH-527 zero-config attribution").

Idea: build `issue_key → project` and consult it in the classification chain
above `match_terms`. Two stages:

1. **Now, zero new config:** invert `build_issue_key_map` (profiles that declare
   `jira_issue_key`), plus `GH-\d+` → the repo's own profile via the existing
   `repo` anchor.
2. **When Jira pull lands** (the direction note ranks Jira→Gittan as the
   prioritized direction):
   the pulled issue list gives `KEY → jira project → gittan profile` for *every*
   issue, not just the declared one. That single adapter turns every branch,
   commit and PR title into a precise attribution key — and it is the same data
   CFO scenario 1 ("plan vs verklighet per issue/epic") needs anyway.

This is the highest-leverage item on the list: it serves detection, the
prioritized integration direction, and the invoice-defence story with one pull.

### I3 — Neighbour proposal, never silent

An `Uncategorized` chat row sitting inside a session that is otherwise
confidently attributed (repo anchor, issue key) is almost always the same work.
Propose that project in `gittan review`; never assign it.

Precedent to copy, not invent: `core/worklog_enrich.py::_nearest_session_label`
already does the ordered-scan + lookback + safety-filter shape — it borrows
*labels within a project*. This borrows *a project across a time gap*, which is
strictly weaker evidence, hence proposal-only. Reuse the `proposed` state name
from `reported_time`.

Guardrail: never propose across a customer boundary without showing both.

### I4 — Worklog as backup truth (answers the original brief's open question)

`TIMELOG.md` is `PRIMARY_CLAIM` in `core/sources.py` — the strongest role in the
policy — yet it only produces events. A worklog line carries *a human's own
statement of project and time*, which is exactly the ground truth every other
signal is approximating.

Idea: a worklog entry's project + its time bracket becomes a **proposal** for
uncategorized rows inside that bracket. Not an assignment: the worklog says what
the operator *claims*, the evidence says what was *observed*, and the whole point
of the review gate is that those two are compared rather than merged. Where they
agree, the row is answered with no question asked; where they disagree, the
disagreement is the useful output.

### I5 — Negative bindings

Bind a thread to "not billable" (a reserved project name, e.g. `__noise__`), so
review stops re-asking about the same personal thread every week. Same store,
same precedence rules, ~10 lines. Without it, R2.3's new grey rows turn the
review queue into a chore, and a chore stops being run.

### I6 — `record_id` on the binding log, now

Intent records have no id. A multi-device union today would have to dedupe on
whole-record equality — fragile the moment a field is added. Adding
`record_id = hash(key_kind, key, project, captured_at, via)` costs ~5 lines
*now* and makes the log's union idempotent, which is precisely §6 step 2–3 of the
direction note (approve layer + idempotent post via a stable evidence id, then
append-only → possibly CRDT).

The binding log is also the *right first thing to sync*: it is small, it is
decisions rather than raw logs (per §3: "synka ledger/beslut först; råloggar
sekundärt"), and append-only + latest-wins-per-key is already a working CRDT for
this shape — a `(key_kind, key)` register with LWW, no HLC needed until two
devices bind the same thread in the same second.

### I7 — Binding usage audit

`core/projects_audit.py` counts which `match_terms` and `tracked_urls` actually
fired. Bindings need the same: which fired, which are dead, which thread was
bound but never observed again (an open question already raised in
`docs/specs/intent-capture.md`). Otherwise the binding layer rots exactly the way
a stale `match_terms` list does, only invisibly.

### I8 — Lint generic profile names

`normalize_profile` auto-indexes the profile `name` as a 1.0-weight term. A name
like `gittan`, `app` or `web` is a common word that will match unrelated text
forever. `core/projects_lint.py` should warn on a single-token name below a
length/commonness floor — the same instinct as `is_over_broad_tracked_url`, one
field over. Cheap, and it is the "undvik generiska termer som enda nyckel" rule
made mechanical.

### I9 — Freeze the title at first sighting

Related to spike #354 (point-in-time capture): store the title as observed the
first time a thread is seen, in the evidence store, and treat later re-titling as
display-only. With I1 (id as key) this is a nicety; without I1 it is what keeps a
title binding from silently detaching. Do I1 first.

### Ranking

| Idea | Value | Cost | Do when |
| --- | --- | --- | --- |
| I2 stage 1 (issue keys from profiles) | high | low | now |
| I1 (thread id as key) | high | low | with R1 |
| I6 (`record_id`) | medium (high later) | trivial | now — it gets expensive as a migration |
| I8 (generic-name lint) | medium | trivial | now |
| I5 (negative bindings) | medium | low | with R2.3, or the queue rots |
| I3 / I4 (neighbour + worklog proposals) | high | medium | after the review surface exists |
| I2 stage 2 (Jira pull) | very high | high | the Jira context-in track |
| I7 (binding audit) | medium | low | once bindings are in real use |
| I9 (freeze title) | low, given I1 | medium | only if I1 is skipped |

---

## 11. Reconciliation with the documented matching order

`docs/product/agent-context.md` states the intended priority order:

1. `tracked_urls` / explicit binding
2. Specific `match_terms` — long unique strings, e.g. a full chat title
3. Git issue keys / branch keys
4. Weak alone: short names, e.g. a Grok **Project** folder called "Gittan"
5. Worklog manual line as backup truth

That is a **ladder**: rank 1 wins over rank 2 regardless of how much rank-2
evidence there is. The shipped matcher is a **summed score** (§1.2). The two are
not the same algorithm, and the difference is not cosmetic — it changes which
customer an hour is billed to. Five concrete divergences:

| # | Documented | Implemented | Effect |
| --- | --- | --- | --- |
| **D1** | `tracked_urls` / binding outranks everything | `tracked_urls` scores 2.0 and is **summed** with everything else | Three ordinary `match_terms` (3.0) beat the explicit URL binding (2.0). The most deliberate signal in the config loses to three casual ones. |
| **D2** | *Specific* terms — long unique strings — rank above ordinary ones | Every `match_terms` entry scores 1.0 regardless of length; length only breaks ties (rank element 3) | A full chat title and a three-letter term carry identical weight. The word "specific" has no mechanical meaning today. |
| **D3** | Git issue keys / branch keys rank 3 | **Not a classification signal at all** — `extract_issue_key` / `build_issue_key_map` exist but serve only worklog posting | The highest-precision token in the system is unused for attribution (see I2). |
| **D4** | Short names are *weak alone* | The profile `name` scores a full 1.0, same as any term; `GENERIC_TOOL_TERMS` is a hardcoded list of tool names (jira, toggl, cloudflare), not a shortness or weakness rule | A profile called `gittan` matches every mention of the word at full strength — the exact failure the ladder's rank 4 exists to prevent (see I8). |
| **D5** | Worklog manual line is backup truth | `TIMELOG.md` is `PRIMARY_CLAIM` by *role*, but its events go through the same matcher as everything else; there is no backup-truth layer | The one source carrying a human's own statement of project and time cannot rescue anything (see I4). |

### What this changes in this survey

- **Q5 is no longer an open question.** It was filed as "a separate decision is
  owed on whether `tracked_urls` should dominate rather than outweigh". The
  decision is on record: it should dominate. Q5 becomes **D1**, a defect against
  documented intent, not a design question. It is now the most valuable single
  fix here, because it silently caps the value of every signal added on top.
- **I2 and I4 are promoted from ideas to requirements.** Issue keys (rank 3) and
  worklog backup truth (rank 5) are documented positions in the intended order,
  not proposals. Their ranking in §10 stands; their status does not.
- **I8 gains a documented mandate** — rank 4 says short names are weak alone, and
  nothing in the code says so.
- **§9's vocabulary collision is settled.** The agent-context table names the
  concept **`binding`** and says a future MCP surface must write the same binding
  store. The code's `intent` is that store. Rename or alias it; do not add a
  second one.
- **R1 is consistent with the ladder.** Rank 2 endorses a full chat title as a
  `match_terms` entry, which works but is a permanent text rule. Rank 1 —
  binding — is the same answer with reversal and provenance, so R1 puts the title
  case one rung higher than the minimum the ladder allows. Where a thread id
  exists, I1 makes that rung exact.

### Suggested order of work

D1 first: it is the smallest change (a comparison rule in
`core/domain.py::classify_project`) with the largest correctness effect, and it
is required before D2–D5 mean anything — adding a high-precision signal to a
summed score just adds another addend. Then D3 (I2 stage 1), then D4 (I8), then
D5 (I4), which needs the review surface.
