#!/usr/bin/env bash
# rabbit_handoff.sh — the NEEDS_HUMAN → board handoff for the kanin-loop.
#
# When `scripts/rabbit_loop.sh` has CONVERGED but the change is NEEDS_HUMAN, the
# work is machine-clean yet still needs a human's eyes (report/invoice numbers,
# visual output, packaging, governance). This script parks the linked issue in the
# project board's **"Needs manual testing"** column and posts the generated
# manual-test checklist as an issue comment — so the pause has a concrete,
# runnable destination instead of living only in a terminal.
#
# It is the only kanin-loop script that WRITES to GitHub. `rabbit_loop.sh` stays a
# pure read-only critic; this mutating step is separate and explicit.
#
# Usage:
#   scripts/rabbit_handoff.sh --issue N [--base origin/main]
#                             [--project 3] [--owner mbjorke]
#                             [--status "Needs manual testing"]
#                             [--dry-run] [--force] [--help]
#
# Defaults target GitHub Project 3 (github.com/users/mbjorke/projects/3). All
# board IDs are resolved BY NAME at run time, so renaming a field/option here does
# not break the script (as long as --status matches the column's name).
#
# --force   proceed even if the diff classifies SAFE (SAFE normally auto-merges and
#           does not need the column).
# --dry-run print what would happen; make no board write and post no comment.
#
# Requires: gh (with the `project` scope — `gh auth refresh -s project`), a
# CONVERGED stamp (`.rabbit-loop/converged.ack` written by `rabbit_loop.sh` on
# RABBIT_LOOP: CONVERGED), and a clean committed branch. Exit codes: 0 = handed
# off (or dry-run), 2 = setup/usage problem, 3 = refused (SAFE without --force).
set -euo pipefail

BASE="origin/main"
PROJECT="3"
OWNER="mbjorke"
STATUS="Needs manual testing"
ISSUE=""
DRY_RUN=0
FORCE=0

usage() { awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue)   [[ $# -ge 2 ]] || { echo "rabbit_handoff: --issue needs a number" >&2; exit 2; }; ISSUE="$2"; shift 2 ;;
    --base)    [[ $# -ge 2 ]] || { echo "rabbit_handoff: --base needs a branch" >&2; exit 2; }; BASE="$2"; shift 2 ;;
    --project) [[ $# -ge 2 ]] || { echo "rabbit_handoff: --project needs a number" >&2; exit 2; }; PROJECT="$2"; shift 2 ;;
    --owner)   [[ $# -ge 2 ]] || { echo "rabbit_handoff: --owner needs a login" >&2; exit 2; }; OWNER="$2"; shift 2 ;;
    --status)  [[ $# -ge 2 ]] || { echo "rabbit_handoff: --status needs a column name" >&2; exit 2; }; STATUS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force)   FORCE=1; shift ;;
    -h|--help) usage ;;
    *) echo "rabbit_handoff: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_handoff: not inside a git repository" >&2; exit 2; }
cd "$REPO_ROOT"

[[ -n "$ISSUE" ]] || { echo "rabbit_handoff: --issue N is required (the linked GitHub issue)." >&2; exit 2; }
command -v gh >/dev/null 2>&1 || { echo "rabbit_handoff: gh CLI not found." >&2; exit 2; }
if ! gh auth status 2>&1 | grep -q "project"; then
  echo "rabbit_handoff: gh is missing the 'project' scope. Run: gh auth refresh -s project" >&2
  exit 2
fi

# The classify + checklist below reflect the *committed* diff (origin/main...HEAD),
# so uncommitted changes would be parked invisibly. Refuse a dirty worktree.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "rabbit_handoff: working tree is dirty. Commit (or stash) first — the handoff" >&2
  echo "  reflects the committed diff, so uncommitted changes would not be covered." >&2
  exit 2
fi

LOOP="$REPO_ROOT/scripts/rabbit_loop.sh"
[[ -x "$LOOP" ]] || { echo "rabbit_handoff: $LOOP not found/executable." >&2; exit 2; }

# --- 0. gate: prove CONVERGED on this HEAD (findings=0 + tests=PASS) ----------
# --classify-merge alone is not enough; refuse to park unless the loop converged.
CONVERGED_ACK="$REPO_ROOT/.rabbit-loop/converged.ack"
HEAD_NOW="$(git rev-parse HEAD)"
BR_NOW="$(git branch --show-current)"
if [[ ! -f "$CONVERGED_ACK" ]]; then
  echo "rabbit_handoff: no converged.ack — run scripts/rabbit_loop.sh until" >&2
  echo "  RABBIT_LOOP: CONVERGED (findings=0 tests=PASS) on this commit first." >&2
  exit 2
fi
read -r ack_br ack_sha _ts <"$CONVERGED_ACK" || true
if [[ "$ack_br" != "$BR_NOW" || "$ack_sha" != "$HEAD_NOW" ]]; then
  echo "rabbit_handoff: converged.ack is stale ($ack_br @ ${ack_sha:0:7})." >&2
  echo "  Re-run scripts/rabbit_loop.sh on $BR_NOW @ ${HEAD_NOW:0:7}." >&2
  exit 2
fi
set +e
bash scripts/run_autotests.sh >/dev/null 2>&1
TESTS_RC=$?
set -e
if [[ $TESTS_RC -ne 0 ]]; then
  echo "rabbit_handoff: autotests no longer pass — re-run the kanin-loop before handoff." >&2
  exit 2
fi

# --- 1. gate: only NEEDS_HUMAN belongs in the manual-testing column -----------
# Fail closed: proceed only on an explicit MERGE_CLASS verdict. A classifier error
# (no MERGE_CLASS line) must never be read as "safe to park". Note --classify-merge
# exits 1 for NEEDS_HUMAN by design, so a non-zero exit is NOT a failure here — the
# verdict line (checked below), not the exit code, decides.
CLASS_OUT="$("$LOOP" --classify-merge --base "$BASE" || true)"
echo "$CLASS_OUT"
if grep -q "MERGE_CLASS: NEEDS_HUMAN" <<<"$CLASS_OUT"; then
  :   # expected case — this is exactly what the column is for
elif grep -q "MERGE_CLASS: SAFE" <<<"$CLASS_OUT"; then
  if [[ $FORCE -eq 0 ]]; then
    echo "rabbit_handoff: diff is SAFE — it auto-merges when CONVERGED and does not need" >&2
    echo "  the manual-testing column. Pass --force to park it there anyway." >&2
    exit 3
  fi
  echo "rabbit_handoff: SAFE diff, but --force given — proceeding."
else
  echo "rabbit_handoff: could not classify the diff (no MERGE_CLASS verdict from" >&2
  echo "  rabbit_loop.sh --classify-merge). Failing closed — nothing written." >&2
  exit 2
fi

# --- 2. the concrete checklist (must be filled in before this pause is useful) -
PLAN="$("$LOOP" --manual-test-plan --base "$BASE")"

# --- 3–5. park issue on the board (+ PR when present) -------------------------
BOARD_PY="$REPO_ROOT/scripts/rabbit_board.py"
[[ -f "$BOARD_PY" ]] || { echo "rabbit_handoff: $BOARD_PY not found." >&2; exit 2; }

ISSUE_URL="$(gh issue view "$ISSUE" --json url --jq '.url' 2>/dev/null)" \
  || { echo "rabbit_handoff: issue #$ISSUE not found." >&2; exit 2; }

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "DRY RUN — would:"
  echo "  • set #$ISSUE board Status → '$STATUS'"
  python3 "$BOARD_PY" --owner "$OWNER" --project "$PROJECT" --url "$ISSUE_URL" --status "$STATUS" --dry-run
  set +e
  BOARD_SYNC_OUT="$("$REPO_ROOT/scripts/rabbit_board_sync.sh" --status "$STATUS" --owner "$OWNER" --project "$PROJECT" --dry-run 2>&1)"
  BOARD_SYNC_RC=$?
  set -e
  [[ -n "$BOARD_SYNC_OUT" ]] && echo "$BOARD_SYNC_OUT"
  if [[ $BOARD_SYNC_RC -ne 0 && $BOARD_SYNC_RC -ne 3 ]]; then
    echo "rabbit_handoff: PR board sync dry-run failed (exit $BOARD_SYNC_RC)." >&2
    exit 2
  fi
  echo "  • post the manual-test checklist as a comment on #$ISSUE"
  echo ""
  echo "--- checklist preview ---"
  echo "$PLAN"
  exit 0
fi

python3 "$BOARD_PY" --owner "$OWNER" --project "$PROJECT" --url "$ISSUE_URL" --status "$STATUS"

# Same Status for the open PR on this branch (if any) — keeps PR visible on the board.
set +e
BOARD_SYNC_OUT="$("$REPO_ROOT/scripts/rabbit_board_sync.sh" --status "$STATUS" --owner "$OWNER" --project "$PROJECT" 2>&1)"
BOARD_SYNC_RC=$?
set -e
if [[ $BOARD_SYNC_RC -ne 0 && $BOARD_SYNC_RC -ne 3 ]]; then
  [[ -n "$BOARD_SYNC_OUT" ]] && echo "$BOARD_SYNC_OUT" >&2
  echo "rabbit_handoff: PR board sync failed (exit $BOARD_SYNC_RC)." >&2
  exit 2
fi

COMMENT="$(printf '%s\n\n%s\n\n---\n_Parked in **%s** by the kanin-loop NEEDS_HUMAN handoff (`scripts/rabbit_handoff.sh`). Complete each step with a real command + a judgeable expected outcome, run it, then move to **Done**._\n' \
  "🔎 **Manual testing needed before merge** — this change is CONVERGED (CodeRabbit clean, tests green) but touches a human-judgment surface." \
  "$PLAN" "$STATUS")"
gh issue comment "$ISSUE" --body "$COMMENT" >/dev/null

echo ""
echo "rabbit_handoff: #$ISSUE → board Status '$STATUS'; checklist posted as a comment."
