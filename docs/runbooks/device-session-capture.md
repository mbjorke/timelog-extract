# Runbook: capture session evidence from another device

Status: active
Last updated: 2026-07-26
Spec: `docs/task-prompts/device-session-capture-task.md`

Use this when work happened somewhere other than your main machine — a cloud
session, a second laptop, a borrowed machine — and you want those hours in the
ledger instead of losing them.

## On the device that did the work

```bash
gittan capture --dry-run          # what would be captured, writes nothing
gittan capture                    # append to this device's ledger
```

Three surfaces are captured by default: `claude-code` (Claude Code transcripts),
`desktop-code` (Claude Desktop in Code mode), and `cursor` (Cursor composer /
workspace sessions). All three carry a repo or workspace anchor, so the work
attributes itself. Narrow the run with `--source`, repeatable:

```bash
gittan capture --source desktop-code
gittan capture --source cursor
```

An unknown name lists the valid ones, and every run prints which sources actually
contributed — so "0 events" never leaves you guessing which surface was empty.

If that device keeps its own ledger (your second laptop), you are done.

If it does **not** — a cloud container is reclaimed when the session ends —
export instead, and move the file off the device before it disappears:

```bash
gittan capture --device claude-web --export ~/session-2026-07-25.jsonl
```

`--device` is free text; it labels the evidence. Keep labels **unique** across
machines that share one data repo — a collision puts two devices in the same
month file and reintroduces merge breakage. The default is the host name, which
for a container is a random string — naming it yourself makes the ledger readable
later.

## On your main device

```bash
gittan evidence --import ~/session-2026-07-25.jsonl
gittan evidence                   # confirm: record count, chain integrity
```

Import is idempotent. Running it twice, or importing an export that overlaps one
you already merged, appends nothing the second time — the report tells you how
many were already present.

## Reading a transcript from a mounted or copied home

`--home` points capture at a different home directory, so you can capture from a
backup, a mounted volume, or a copied `~/.claude` tree:

```bash
gittan capture --home /Volumes/backup/home-old --device old-laptop
```

## Sharing one `~/.gittan` repo across devices

If your devices share the `~/.gittan` data repo (see
`docs/runbooks/gittan-data-autocommit.md`), you may not need export/import at
all — commit and pull instead. Evidence is filed per device
(`2026-07.laptop.jsonl`, `2026-07.phone.jsonl`) when those labels stay distinct,
so two devices do not write the same file and git has nothing to merge.

`gittan capture` defaults include **Cursor** as well as Claude Code / Desktop
Code (`--source cursor` to limit). Report project/session labels append a short
device list only when **two or more** devices contributed to that project in the
window (`project-alpha (Mac, iPhone)`); a single-device day stays quiet. Billing
project keys are unchanged.

If you have an **older store** where both devices appended to one `2026-07.jsonl`
and git merged them, the hash chain is broken even though every record is real.
Fix it once:

```bash
gittan evidence              # Chain integrity: BROKEN
gittan evidence --repair     # re-links chains, drops duplicates
gittan evidence              # Chain integrity: OK
```

Repair never drops a unique observation, and running it twice changes nothing.

## When a session has no project

Some sessions carry hours but nothing that says whose work it was — a chat with no
repo and no working directory. Rather than adding a `match_term` (a rule that then
matches every future event containing that text), bind the session itself:

```bash
gittan intent                       # walks today's unattributed sessions and asks
gittan intent --list                # current bindings, newest first
gittan intent --set abc123="Customer X"   # non-interactive
```

The answer goes to `~/.gittan/intent-capture.jsonl`, append-only, inside the data
repo you already commit. Re-answering appends a new record and the later one wins,
so the history of what you decided when stays readable. A bound row shows up in
the report under that project, and carries `project_from: intent` so you can tell
a decision from a text match later.

Only sessions Gittan captured can be asked about — the mobile app still leaves
nothing to bind.

## What this does and does not cover

- **Covers:** Claude Code CLI session transcripts, Claude Desktop Code mode, and
  Cursor sessions on any device you can run `gittan` on, including cloud
  containers.
- **Which surface to work in, if the hours are billable:** Claude Code, Claude
  Desktop **Code mode**, and Cursor all carry a repo or workspace anchor, so the
  work attributes itself. Desktop **plain chat** gives correct hours but lands on
  `Uncategorized` unless you happen to type the project name. Measured in
  `docs/evals/claude-surface-attribution-measurement.md`.
- **Does not cover:** the Claude mobile app. It leaves no local artifact on any
  device you control, so there is nothing to read. That gap needs intent capture
  (`docs/specs/intent-capture.md`), not this command.
- **Never duplicates:** an event's identity is source + timestamp + detail, not
  the device that saw it, so the same session captured on two devices lands as
  one record.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Events found: 0` | No transcripts in that window under the chosen `--home`. Check the date range and the path. |
| `no such export file` | `--import` path is wrong, or the file never left the device that wrote it. |
| Import appends 0 every time | Expected when the records are already in the ledger — check `gittan evidence` for the record count. |
| `--export` and `--erase` rejected together | The `evidence` data controls are mutually exclusive by design; run one at a time. |
