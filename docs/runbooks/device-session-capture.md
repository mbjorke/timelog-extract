# Runbook: capture session evidence from another device

Status: active
Last updated: 2026-07-25
Spec: `docs/task-prompts/device-session-capture-task.md`

Use this when work happened somewhere other than your main machine — a cloud
session, a second laptop, a borrowed machine — and you want those hours in the
ledger instead of losing them.

## On the device that did the work

```bash
gittan capture --dry-run          # what would be captured, writes nothing
gittan capture                    # append to this device's ledger
```

If that device keeps its own ledger (your second laptop), you are done.

If it does **not** — a cloud container is reclaimed when the session ends —
export instead, and move the file off the device before it disappears:

```bash
gittan capture --device claude-web --export ~/session-2026-07-25.jsonl
```

`--device` is free text; it labels the evidence. The default is the host name,
which for a container is a random string — naming it yourself makes the ledger
readable later.

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
(`2026-07.laptop.jsonl`, `2026-07.phone.jsonl`), so two devices never write the
same file and git has nothing to merge.

If you have an **older store** where both devices appended to one `2026-07.jsonl`
and git merged them, the hash chain is broken even though every record is real.
Fix it once:

```bash
gittan evidence              # Chain integrity: BROKEN
gittan evidence --repair     # re-links chains, drops duplicates
gittan evidence              # Chain integrity: OK
```

Repair never drops a unique observation, and running it twice changes nothing.

## What this does and does not cover

- **Covers:** Claude Code CLI session transcripts on any device you can run
  `gittan` on, including cloud containers.
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
