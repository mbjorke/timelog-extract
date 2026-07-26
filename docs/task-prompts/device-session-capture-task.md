# Device session capture — evidence that survives the machine it happened on

Gittan reconstructs a day from artifacts that happen to survive on **one**
machine. That premise breaks the moment work moves. A session run from a phone,
or in a cloud container, writes its transcript on *that* device — and a container
is reclaimed when the session ends. The evidence is not weak or ambiguous; it is
simply somewhere else, briefly.

The operator's framing, and the one this spec adopts: **a phone is a machine
too.** "Local-first" means the operator's devices, not the operator's laptop.

## Measured gap (2026-07-25)

A synthetic remote-session fixture, measured with the existing collector against
a container-shaped transcript (neutral project slug; no live customer data):

| Path | Result |
|---|---|
| `collect_claude_code` over the session transcript | dozens of events → one session, sub-hour span, correctly attributed |
| GitHub public events for the same synthetic work | a handful of push timestamps → shorter span after the `min_session` floor |

The raw span matched the transcript's own span exactly — no inference involved.
The artifact parses today; nothing needed inventing. What was missing was
**durability across devices**.

## Behavior

```gherkin
Feature: Session evidence survives the device that produced it
  A day's work is recoverable even when the machine that did it is gone.

  Scenario: A device captures its own session evidence
    Given this device holds AI session transcripts for today
    When the operator runs gittan capture
    Then the events are appended to the evidence ledger
    And each record carries the device that observed it

  Scenario: A device whose store is not canonical exports instead
    Given a cloud container that will be reclaimed
    When the operator runs gittan capture --export PATH
    Then ledger-shaped records are written to PATH
    And the local store is left untouched

  Scenario: Another device's evidence merges without double counting
    Given an export produced on another device
    When the operator runs gittan evidence --import PATH
    Then new records are appended to this device's ledger
    And records already present are skipped

  Scenario: The same session seen by two devices is one record
    Given the same session is captured on a laptop and on a phone
    When both captures reach the same ledger
    Then the work appears once
    And the device that observed it first is preserved

  Scenario: Dry run writes nothing anywhere
    Given any device state
    When the operator runs gittan capture --dry-run
    Then the counts are reported
    And no store, export file, or directory is created
```

## Design decisions

**Device lives in `source_provenance`, not in a new field.** The slot already
exists on every record. No schema bump, and — crucially — the fingerprint stays
`source + observed_at + detail`, so the *same event* observed from two devices
dedupes to one record. Identity is what happened, not who noticed.

**Capture reuses collectors, it does not add a source.** `collect_claude_code`
already takes a `home`; capture points it at the device's home and tags the
result. A new capture source is a new entry in `CAPTURE_SOURCES`, not new
parsing.

**Evidence is filed per device.** Records land in `YYYY-MM.<device>.jsonl`, so
two devices with *distinct* device labels sharing one `~/.gittan` git repo never
write the same file. Labels must stay unique per machine (`--device` overrides
the host name); a collision recreates the merge problem this layout avoids.
Measured before choosing this: two healthy chains merged the way git resolves a
conflict produce `chain_ok: False` while every record stays genuine. Removing
the collision beats resolving it; `gittan evidence --repair` exists for stores
that already hit it. See `docs/decisions/private-not-local.md`.

**Export/import over sync.** A device that cannot own the canonical ledger writes
portable records; the canonical device merges them. Both directions carry the
same records and `capture_events` is idempotent, so a merge is safe at any
frequency. No daemon, no network, no account.

**No titles become identity.** Records carry timestamps, source, the detail line
the collector already produced, and the device. Promoting a live chat title to
hours identity stays out of scope (`#354`'s do-not-build rule); this spec does
not touch it.

## Surfaces

- `gittan capture [--from D] [--to D] [--device NAME] [--home PATH]
  [--export PATH] [--dry-run] [--source NAME]… [--projects-config PATH]`
- Captured surfaces (`CAPTURE_SOURCES`): `claude-code`, `desktop-code`.
  `--source` is repeatable and selects a subset; an unknown name lists the valid
  ones. The run reports which sources actually contributed.
- `gittan evidence --import PATH` — the natural pair to the existing
  `--export`, and mutually exclusive with the other data controls.
- `gittan evidence --repair` — re-link chains for a store merged by git.
- `gittan capture --if-enabled` — the automation form: respects the persistent
  `shadow_log` setting so a timer never writes evidence nobody enabled. The
  `~/.gittan` autocommit timer runs it each tick before committing.
- `gittan doctor` → **Device coverage** row: which devices reach the ledger and
  when each was last seen; quiet for more than 10 days is flagged.

## Known limits

- Captures the two surfaces that carry a **structural** project anchor:
  `claude-code` (repo slug from `cwd`) and `desktop-code` (repo slug from the
  session's git metadata, worktree-invariant). Plain desktop chat is left out on
  purpose — measured 2026-07-26
  (`docs/evals/claude-surface-attribution-measurement.md`), it produces honest
  hours with no anchor at all, so it lands on `Uncategorized` unless the operator
  happened to type the project name. Adding it later is one registry entry, with
  eyes open about that.
- **Cursor is not in `CAPTURE_SOURCES` yet** — live same-machine Cursor rows
  still appear via collectors, but durable cross-device capture does not. Device
  is stored in provenance and shown in doctor, **not** appended to report
  project/session labels. Both gaps: #474 /
  `docs/task-prompts/capture-cursor-and-device-labels-task.md`.
- The Claude **mobile app** writes no local artifact on any device the operator
  controls, so it stays uncaptured. Closing that needs intent capture
  (`docs/specs/intent-capture.md`), which is a different mechanism.
- A remote session's evidence is *reported by* that session rather than observed
  on the operator's own machine. The timestamps are mechanical rather than
  self-assessed, and the ledger stays append-only and hash-chained — but the
  evidence-role question belongs to `docs/specs/source-evidence-policy.md` and is
  left open here rather than silently answered.

## Traceability

- story_id: `GH-470` (https://github.com/mbjorke/timelog-extract/issues/470)
- covers: capture
- spec_status: approved
- implementation_status: built
- created_at: 2026-07-25
- last_updated_at: 2026-07-26
- implementation.pr: https://github.com/mbjorke/timelog-extract/pull/469
- implementation.branch: task/session-capture-and-intent
- implementation.commits: []
- validation.evidence: `tests/test_session_capture.py` (cross-device dedupe and
  dry-run write-nothing), `tests/test_cli_evidence_ux.py` (import error pattern);
  fixture export/import round-trip with 0 duplicates and chain integrity OK
- validation.decision: conditional GO
- changelog:
  - 2026-07-25: Initial spec and implementation. `gittan capture` +
    `gittan evidence --import`, device provenance in the existing
    `source_provenance` slot.
  - 2026-07-25: Per-device ledger filing (`YYYY-MM.<device>.jsonl`) so a shared
    `~/.gittan` repo has nothing to merge, plus `gittan evidence --repair` for
    stores already merged by git.
  - 2026-07-25: Continuity — `--if-enabled` gate, capture wired into the
    `~/.gittan` autocommit timer, and a doctor Device-coverage row so a device
    that stopped reporting is visible instead of silently absent.
  - 2026-07-26: Measured attribution signal per Claude surface; recorded which
    surface is worth capturing next and why chat-shaped work cannot be fixed by
    capture alone.
  - 2026-07-26: Added `desktop-code` to `CAPTURE_SOURCES` (the measurement's
    recommendation) plus a repeatable `--source` selector and a per-run report of
    which sources contributed.
  - 2026-07-26: PO pass — story_id was wrongly `GH-464` (collided with an
    unrelated closed issue). Correct tracker is #470; PR #469. Board Status
    → Needs manual testing until the maintainer walkthrough lands.
