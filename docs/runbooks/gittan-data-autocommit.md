# Runbook: auto-commit the local gittan data dir

Version-control `~/.gittan` (config, `observed/` + `reported/` caches, invoice
`ledger.yaml`, worklogs) on a short timer so nothing can be lost unrecoverably.

**Why:** incident
[`2026-07-01-observed-cache-overwrite-degrades-closed-months.md`](../incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md)
— the observed cache was untracked, so report runs (and a concurrent `git clean`)
silently wiped closed-month data with no history to restore. Once files are
**committed**, `git clean` can't touch them and any bad write is one `git checkout`
away from recovery.

## What it does

`scripts/gittan_data_autocommit.sh` — from the data dir (`GITTAN_HOME`, default
`~/.gittan`): if there are changes, `git add -A` + `git commit -m "auto: <ts>"`.
**Commit-only by default** (everything stays local). Best-effort and non-fatal: a
concurrent git op just means it retries next tick.

- `GITTAN_HOME` — data dir (default `~/.gittan`).
- `GITTAN_AUTOCOMMIT_PUSH=1` — also `git push` to the remote. Off by default. Only
  enable this if the remote is **private** (the dir holds customer/invoice data).

## One-time setup

The data dir must already be a git repo (`git -C ~/.gittan init` if not). Then
install the timer.

### macOS (launchd)

Save this as `~/Library/LaunchAgents/sh.gittan.autocommit.plist` and load it
(replace the script path with your checkout, and `USERNAME`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>sh.gittan.autocommit</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/USERNAME/Workspace/Project/timelog-extract/scripts/gittan_data_autocommit.sh</string>
  </array>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/gittan-autocommit.log</string>
  <key>StandardErrorPath</key><string>/tmp/gittan-autocommit.log</string>
</dict>
</plist>
```

```bash
launchctl load -w ~/Library/LaunchAgents/sh.gittan.autocommit.plist
```

Enable off-machine backup to a **private** remote by adding before `</dict>`:

```xml
  <key>EnvironmentVariables</key><dict><key>GITTAN_AUTOCOMMIT_PUSH</key><string>1</string></dict>
```

Uninstall: `launchctl unload ~/Library/LaunchAgents/sh.gittan.autocommit.plist`.

### Linux (cron)

```cron
*/10 * * * * /path/to/timelog-extract/scripts/gittan_data_autocommit.sh
```

## Verify

- `bash scripts/gittan_data_autocommit.sh` once → `git -C ~/.gittan log -1` shows an
  `auto:` commit (or nothing, if the tree was clean).
- Make a change under `~/.gittan`, wait one interval, confirm a new `auto:` commit.
- `~/.gittan/observed/` and `reported/` are tracked (`git -C ~/.gittan ls-files observed/`).

## Notes

- The data dir is **local-first**: keep any remote **private** — it contains
  customer names, hours, and invoice records. Never add a public remote.
- Transient temp files (`.tmp_*` written by the observed-cache atomic swap) are
  short-lived; if they add noise, add them to `~/.gittan/.gitignore`.
