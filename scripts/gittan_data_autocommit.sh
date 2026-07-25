#!/usr/bin/env bash
# Auto-commit the local gittan data dir so config, observed/reported caches, the
# invoice ledger, and worklogs are always versioned — and can never be lost
# unrecoverably again (incident docs/incidents/2026-07-01-observed-cache-overwrite-degrades-closed-months.md).
#
# Meant to run on a short timer (launchd / cron) — see
# docs/runbooks/gittan-data-autocommit.md. Best-effort and non-fatal: if a
# concurrent git op holds index.lock, add/commit fails and we retry next tick.
# Committed files survive any `git clean` a concurrent tool may run.
#
# Captures first, then commits: preserving an empty dir is not durability. The
# capture step is gated on "shadow_log": "on" (via --if-enabled), so a timer never
# starts writing evidence the operator did not turn on.
#
#   GITTAN_HOME                 data dir (default: ~/.gittan)
#   GITTAN_AUTOCOMMIT_PUSH=1    also push to the (private) remote — off by default;
#                               commit-only keeps everything local.
#   GITTAN_AUTOCOMMIT_CAPTURE=0 skip the capture step (commit-only, previous behavior)
#   GITTAN_BIN                  gittan executable (default: first on PATH)
set -uo pipefail

DATA_DIR="${GITTAN_HOME:-$HOME/.gittan}"

# Capture this device's session evidence before committing. Best-effort: a
# missing binary or a failed capture must never block the commit that follows,
# and --if-enabled makes it a no-op unless the operator enabled the shadow log.
if [ "${GITTAN_AUTOCOMMIT_CAPTURE:-1}" = "1" ]; then
  GITTAN_CMD="${GITTAN_BIN:-$(command -v gittan 2>/dev/null || true)}"
  if [ -n "$GITTAN_CMD" ] && [ -x "$GITTAN_CMD" ]; then
    "$GITTAN_CMD" capture --if-enabled >/dev/null 2>&1 || true
  fi
fi

cd "$DATA_DIR" 2>/dev/null || exit 0
[ -d .git ] || exit 0

# Nothing changed → nothing to do (keeps the log quiet).
[ -n "$(git status --porcelain 2>/dev/null)" ] || exit 0

git add -A 2>/dev/null || exit 0
git commit -q -m "auto: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || exit 0

if [ "${GITTAN_AUTOCOMMIT_PUSH:-0}" = "1" ]; then
  git push -q 2>/dev/null || true  # best-effort backup to a PRIVATE remote
fi
