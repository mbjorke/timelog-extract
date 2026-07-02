#!/usr/bin/env bash
# rabbit_workflow_context.sh — multi-agent / GitButler workflow preflight for kanin-loop.
#
# Surfaces plain-git vs GitButler mode, sibling worktrees, local branch lanes, and
# branch-name collision risks BEFORE CodeRabbit runs — so agents do not rely on
# `git ls-remote` alone (see GitHub issue #240).
#
# Writes:
#   .rabbit-loop/preflight.json   machine-readable context
#   .rabbit-loop/preflight.html   visual briefing + acknowledgement questions
#   .rabbit-loop/workflow.ack       written by --ack after human/agent confirms
#
# Usage:
#   scripts/rabbit_workflow_context.sh              # summary + artifacts
#   scripts/rabbit_workflow_context.sh --json       # print JSON only
#   scripts/rabbit_workflow_context.sh --chat-summary  # markdown for chat (agents)
#   scripts/rabbit_workflow_context.sh --ack        # acknowledge (records HEAD)
#   scripts/rabbit_workflow_context.sh --ack --force
#
# Exit: 0 = clear, 1 = warnings (ack recommended), 2 = blockers

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "rabbit_workflow_context: not inside a git repository" >&2; exit 2; }
cd "$REPO_ROOT"

# Bounded subprocess (portable on macOS without GNU timeout).
_run_timeout() {
  local secs="$1"; shift
  python3 - "$secs" "$@" <<'PY'
import subprocess, sys
secs = int(sys.argv[1])
cmd = sys.argv[2:]
try:
    subprocess.run(cmd, timeout=secs, check=False)
except subprocess.TimeoutExpired:
    sys.exit(124)
PY
}

LANE_SEP=$'\x1f'

STATE_DIR="$REPO_ROOT/.rabbit-loop"
JSON_FILE="$STATE_DIR/preflight.json"
HTML_FILE="$STATE_DIR/preflight.html"
ACK_FILE="$STATE_DIR/workflow.ack"

JSON_ONLY=0
CHAT_SUMMARY=0
DO_ACK=0
FORCE_ACK=0

usage() {
  awk 'NR>=2 && /^#/{sub(/^# ?/,""); print; next} NR>=2{exit}' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_ONLY=1; shift ;;
    --chat-summary) CHAT_SUMMARY=1; shift ;;
    --ack) DO_ACK=1; shift ;;
    --force) FORCE_ACK=1; shift ;;
    -h|--help) usage ;;
    *) echo "rabbit_workflow_context: unknown arg '$1' (try --help)" >&2; exit 2 ;;
  esac
done

if [[ $JSON_ONLY -eq 1 && $CHAT_SUMMARY -eq 1 ]]; then
  echo "rabbit_workflow_context: use --json or --chat-summary, not both." >&2
  exit 2
fi

mkdir -p "$STATE_DIR"

_read_preflight_counts() {
  python3 - "$1" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
print(len(d.get("blockers", [])), len(d.get("warnings", [])))
PY
}

CURRENT="$(git branch --show-current 2>/dev/null || echo "(detached)")"
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo "")"
DIRTY="$(git status --porcelain 2>/dev/null || true)"

WORKFLOW_MODE="plain_git"
GITBUTLER_PROJECT=0
COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || echo .git)"
[[ "$COMMON_DIR" != /* ]] && COMMON_DIR="$REPO_ROOT/$COMMON_DIR"
[[ -d "$COMMON_DIR/gitbutler" ]] && GITBUTLER_PROJECT=1
if [[ "$CURRENT" == gitbutler/* ]]; then
  WORKFLOW_MODE="gitbutler"
fi

BUT_AVAILABLE=0
command -v but >/dev/null 2>&1 && BUT_AVAILABLE=1

BUT_STATUS=""
BUT_APPLIED=""
if [[ $BUT_AVAILABLE -eq 1 && "$WORKFLOW_MODE" == "gitbutler" ]]; then
  BUT_STATUS="$(but status 2>&1 || true)"
  BUT_APPLIED="$(printf '%s\n' "$BUT_STATUS" | awk '/^[[:space:]]*●|applied|Applied/{print}' | head -20 || true)"
fi

WORKTREES="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' || true)"

# Local task/* lanes — other agents may own these (unit-sep fields; subjects may contain |).
LOCAL_LANES=""
while IFS='|' read -r bname date subj upstream; do
  [[ -z "$bname" ]] && continue
  ahead="0"
  behind="0"
  if [[ -n "$upstream" ]]; then
    counts="$(git rev-list --left-right --count "${upstream}...${bname}" 2>/dev/null || echo "0	0")"
    behind="${counts%%	*}"
    ahead="${counts##*	}"
  fi
  LOCAL_LANES+="${bname}${LANE_SEP}${date}${LANE_SEP}${subj}${LANE_SEP}${upstream}${LANE_SEP}${ahead}${LANE_SEP}${behind}"$'\n'
done < <(
  git for-each-ref --sort=-committerdate refs/heads/task/ \
    --format='%(refname:short)|%(committerdate:iso8601)|%(subject)|%(upstream:short)' 2>/dev/null \
    | head -20 || true
)

# Branch / remote collision hints (local truth beats ls-remote).
COLLISIONS=""
_add_collision() { COLLISIONS+="$1"$'\n'; }

if [[ -n "$CURRENT" && "$CURRENT" != "(detached)" ]]; then
  UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  if [[ -n "$UPSTREAM" ]]; then
    if ! _run_timeout 20 git fetch origin "$CURRENT" 2>/dev/null; then
      _add_collision "fetch_timeout|$CURRENT|origin|git fetch timed out — remote state may be stale; continuing with local refs."
    fi
    LOCAL_TIP="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_TIP="$(git rev-parse "$UPSTREAM" 2>/dev/null || true)"
    if [[ -n "$LOCAL_TIP" && -n "$REMOTE_TIP" && "$LOCAL_TIP" != "$REMOTE_TIP" ]]; then
      # Another local branch may already track the same remote name with different intent.
      while IFS= read -r other; do
        [[ -z "$other" || "$other" == "$CURRENT" ]] && continue
        other_up="$(git rev-parse --abbrev-ref --symbolic-full-name "$other@{u}" 2>/dev/null || true)"
        if [[ "$other_up" == "$UPSTREAM" ]]; then
          _add_collision "local_branch|$other|$CURRENT|Both track $UPSTREAM with different tips — multi-agent collision risk (#240)."
        fi
      done < <(git for-each-ref --format='%(refname:short)' refs/heads/task/ 2>/dev/null || true)
      if git merge-base --is-ancestor "$REMOTE_TIP" "$LOCAL_TIP" 2>/dev/null; then
        : # ahead only — normal
      elif git merge-base --is-ancestor "$LOCAL_TIP" "$REMOTE_TIP" 2>/dev/null; then
        _add_collision "diverged_remote|$CURRENT|$UPSTREAM|Local branch is behind remote — fetch/merge before push."
      else
        _add_collision "diverged_history|$CURRENT|$UPSTREAM|Local and remote have diverged — do not force-push without checking other agents."
      fi
    fi
  fi
  # Reserved lane names: same branch name, different work (lesson from #268).
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    IFS="$LANE_SEP" read -r bname _date subj _up _ah _bh <<< "$line"
    [[ -z "$bname" || "$bname" == "$CURRENT" ]] && continue
    # Same topical words but different branch — warn if remote exists for current name.
    if git rev-parse --verify --quiet "origin/$CURRENT" >/dev/null 2>&1; then
      other_tip="$(git rev-parse "$bname" 2>/dev/null || true)"
      cur_tip="$(git rev-parse "$CURRENT" 2>/dev/null || true)"
      if [[ -n "$other_tip" && -n "$cur_tip" && "$other_tip" != "$cur_tip" ]]; then
        if [[ "$bname" == *board* && "$CURRENT" == *timely* ]] || [[ "$bname" == *timely* && "$CURRENT" == *board* ]]; then
          _add_collision "name_semantics|$bname|$CURRENT|Remote origin/$CURRENT exists; local $bname holds different work — pick a fresh task/* name."
        fi
      fi
    fi
  done <<< "$LOCAL_LANES"
fi

if [[ $GITBUTLER_PROJECT -eq 1 && "$WORKFLOW_MODE" == "plain_git" ]]; then
  _add_collision "mode_mismatch|gitbutler_project|plain_git|.git/gitbutler exists but you are on plain-git branch '$CURRENT' — check applied virtual branches (but status) before push."
fi

if [[ "$WORKFLOW_MODE" == "gitbutler" && $BUT_AVAILABLE -eq 0 ]]; then
  _add_collision "but_missing|gitbutler_branch|no_cli|On $CURRENT but 'but' CLI not found."
fi

OPEN_PRS=""
if command -v gh >/dev/null 2>&1; then
  OPEN_PRS="$(python3 - <<'PY' 2>/dev/null || true
import json, subprocess
try:
    out = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--limit", "15", "--json", "number,headRefName,title,url"],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(0)
    sep = "\x1f"
    for pr in json.loads(out.stdout or "[]"):
        print(sep.join([str(pr["number"]), pr["headRefName"], pr["title"], pr["url"]]))
except subprocess.TimeoutExpired:
    pass
PY
)"
  [[ -z "$OPEN_PRS" ]] && _add_collision "gh_timeout|open_prs|gh|gh pr list timed out or failed — open PR table may be incomplete."
fi

# --- acknowledgement ---------------------------------------------------------
if [[ $DO_ACK -eq 1 ]]; then
  [[ -f "$JSON_FILE" ]] || {
    echo "rabbit_workflow_context: run preflight and review $HTML_FILE before --ack." >&2
    exit 2
  }
  ACK_META="$(python3 - "$JSON_FILE" "$CURRENT" "$HEAD_SHA" <<'PY'
import json, sys
path, current, head = sys.argv[1:4]
d = json.load(open(path))
if d.get("branch") != current or d.get("head") != head:
    sys.exit(3)
print(len(d.get("blockers", [])))
PY
)" || {
    echo "rabbit_workflow_context: preflight is stale/unreadable; regenerate before --ack." >&2
    exit 2
  }
  BLOCKERS_CT="$ACK_META"
  if [[ "$BLOCKERS_CT" -gt 0 && $FORCE_ACK -eq 0 ]]; then
    echo "rabbit_workflow_context: $BLOCKERS_CT blocker(s) — fix or pass --force after review." >&2
    echo "  See $HTML_FILE" >&2
    exit 2
  fi
  printf '%s %s %s\n' "$CURRENT" "$HEAD_SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$ACK_FILE"
  echo "rabbit_workflow_context: acknowledged $CURRENT @ ${HEAD_SHA:0:7}"
  exit 0
fi

# --- emit JSON + HTML via Python --------------------------------------------
export WF_CURRENT="$CURRENT" WF_HEAD="$HEAD_SHA" WF_MODE="$WORKFLOW_MODE"
export WF_GB_PROJECT="$GITBUTLER_PROJECT" WF_BUT_AVAIL="$BUT_AVAILABLE"
export WF_DIRTY="$DIRTY" WF_WORKTREES="$WORKTREES"
export WF_LOCAL_LANES="$LOCAL_LANES" WF_COLLISIONS="$COLLISIONS"
export WF_OPEN_PRS="$OPEN_PRS" WF_BUT_STATUS="$BUT_STATUS" WF_BUT_APPLIED="$BUT_APPLIED"
export WF_LANE_SEP="$LANE_SEP"

python3 - "$JSON_FILE" "$HTML_FILE" <<'PY'
import html
import json
import os
import sys
from datetime import datetime, timezone

json_path, html_path = sys.argv[1], sys.argv[2]

def lines(raw: str) -> list[str]:
    return [ln for ln in (raw or "").splitlines() if ln.strip()]

current = os.environ.get("WF_CURRENT", "")
head = os.environ.get("WF_HEAD", "")
mode = os.environ.get("WF_MODE", "plain_git")
gb_project = os.environ.get("WF_GB_PROJECT") == "1"
but_avail = os.environ.get("WF_BUT_AVAIL") == "1"
dirty = bool(os.environ.get("WF_DIRTY", "").strip())
worktrees = lines(os.environ.get("WF_WORKTREES", ""))

lanes = []
lane_sep = os.environ.get("WF_LANE_SEP", "\x1f")
for ln in lines(os.environ.get("WF_LOCAL_LANES", "")):
    parts = ln.split(lane_sep, 5)
    while len(parts) < 6:
        parts.append("")
    lanes.append({
        "branch": parts[0],
        "date": parts[1],
        "subject": parts[2],
        "upstream": parts[3],
        "ahead": parts[4],
        "behind": parts[5],
        "current": parts[0] == current,
    })

blockers, warnings = [], []
for ln in lines(os.environ.get("WF_COLLISIONS", "")):
    parts = ln.split("|")
    kind = parts[0]
    detail = parts[-1] if len(parts) > 1 else ln
    refs = parts[1:-1]
    entry = {"kind": kind, "detail": detail, "refs": refs}
    if kind in ("diverged_history", "but_missing"):
        blockers.append(entry)
    else:
        warnings.append(entry)

open_prs = []
pr_sep = "\x1f"
for ln in lines(os.environ.get("WF_OPEN_PRS", "")):
    n, br, title, url = (ln.split(pr_sep, 3) + ["", "", "", ""])[:4]
    if n:
        open_prs.append({"number": int(n), "branch": br, "title": title, "url": url})

questions = [
    {
        "id": "mode",
        "prompt": f"Which write mode are you using? (detected: {mode})",
        "options": [
            "plain_git — git commit / git push on this task/* branch",
            "gitbutler — but commit / but push only (no git commit)",
            "worktree — isolated clone; I verified siblings",
        ],
    },
    {
        "id": "branch_intent",
        "prompt": f"Is '{current}' the correct lane for THIS task (not another agent's branch)?",
        "options": ["Yes — I read git log / PR / but status", "No — I need to switch branch or worktree first"],
    },
    {
        "id": "collisions",
        "prompt": "Did you review local task/* lanes and open PRs for name/work collisions?",
        "options": ["Yes — table below looks safe", "No — stopping to reconcile first"],
    },
]
if dirty:
    questions.append({
        "id": "dirty",
        "prompt": "Working tree is dirty. Commit scope matches one virtual branch / one PR?",
        "options": ["Yes", "No — split commits or stash"],
    })

payload = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "branch": current,
    "head": head,
    "workflow_mode": mode,
    "gitbutler_project": gb_project,
    "but_available": but_avail,
    "dirty": dirty,
    "worktrees": worktrees,
    "local_task_lanes": lanes,
    "open_prs": open_prs,
    "blockers": blockers,
    "warnings": warnings,
    "questions": questions,
    "but_status_excerpt": (os.environ.get("WF_BUT_STATUS") or "")[:4000],
    "but_applied": lines(os.environ.get("WF_BUT_APPLIED", "")),
    "ack_command": "scripts/rabbit_workflow_context.sh --ack",
}

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")

def esc(s: str) -> str:
    return html.escape(str(s or ""))

rows = "".join(
    f"<tr class='{'current' if l['current'] else ''}'><td>{esc(l['branch'])}</td>"
    f"<td>{esc(l['date'][:10])}</td><td>{esc(l['subject'][:80])}</td>"
    f"<td>{esc(l['upstream'])}</td><td>{esc(l['ahead'])}/{esc(l['behind'])}</td></tr>"
    for l in lanes
)
pr_rows = "".join(
    f"<tr><td><a href='{esc(p['url'])}'>#{p['number']}</a></td>"
    f"<td><code>{esc(p['branch'])}</code></td><td>{esc(p['title'][:100])}</td></tr>"
    for p in open_prs
)
q_html = ""
for q in questions:
    opts = "".join(f"<li>{esc(o)}</li>" for o in q["options"])
    q_html += f"<div class='card'><h3>{esc(q['prompt'])}</h3><ul>{opts}</ul></div>"

blk = "".join(f"<li><strong>{esc(b['kind'])}</strong>: {esc(b['detail'])}</li>" for b in blockers)
wrn = "".join(f"<li><strong>{esc(w['kind'])}</strong>: {esc(w['detail'])}</li>" for w in warnings)
but_applied = lines(os.environ.get("WF_BUT_APPLIED", ""))
but_applied_html = "".join(f"<li><code>{esc(x)}</code></li>" for x in but_applied) or "<li>(none)</li>"

page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Gittan kanin-loop — workflow preflight</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f0f14; color: #e8e6f0; margin: 2rem; line-height: 1.5; }}
  h1 {{ color: #c4b5fd; }} h2 {{ color: #a78bfa; margin-top: 2rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 6px; background: #2d2640; color: #ddd6fe; }}
  .blocker {{ color: #fca5a5; }} .warn {{ color: #fcd34d; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #3f3f50; padding: 0.5rem; text-align: left; }}
  th {{ background: #1a1a24; }} tr.current {{ background: #1e1b2e; }}
  .card {{ background: #1a1a24; border: 1px solid #3f3f50; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
  code {{ background: #2d2640; padding: 0.1rem 0.3rem; border-radius: 4px; }}
</style></head><body>
<h1>Kanin-loop workflow preflight</h1>
<p>Branch <code>{esc(current)}</code> @ <code>{esc(head[:7])}</code>
<span class="badge">{esc(mode)}</span>
{'<span class="badge warn">dirty</span>' if dirty else ''}</p>
<p>Answer the questions below in chat or terminal, then run:
<code>scripts/rabbit_workflow_context.sh --ack</code></p>
<h2>Blockers</h2>
<ul class="blocker">{blk or '<li>None</li>'}</ul>
<h2>Warnings</h2>
<ul class="warn">{wrn or '<li>None</li>'}</ul>
<h2>Questions</h2>
{q_html}
<h2>Local task/* lanes</h2>
<table><tr><th>Branch</th><th>Date</th><th>Subject</th><th>Upstream</th><th>Ahead/Behind</th></tr>{rows or '<tr><td colspan=5>None</td></tr>'}</table>
<h2>Open PRs</h2>
<table><tr><th>PR</th><th>Head</th><th>Title</th></tr>{pr_rows or '<tr><td colspan=3>None / gh unavailable</td></tr>'}</table>
<h2>GitButler applied (excerpt)</h2>
<ul>{but_applied_html}</ul>
<h2>Worktrees</h2>
<ul>{''.join(f'<li><code>{esc(w)}</code></li>' for w in worktrees) or '<li>Primary clone only</li>'}</ul>
</body></html>"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(page)

import sys
print(json.dumps({"blockers": len(blockers), "warnings": len(warnings)}), file=sys.stderr)
PY

if [[ $JSON_ONLY -eq 1 ]]; then
  cat "$JSON_FILE"
  exit 0
fi

if [[ $CHAT_SUMMARY -eq 1 ]]; then
  python3 "$REPO_ROOT/scripts/rabbit_workflow_context_chat.py" "$JSON_FILE"
  read -r BLOCKERS WARNINGS < <(_read_preflight_counts "$JSON_FILE")
  if [[ "$BLOCKERS" -gt 0 ]]; then exit 2; fi
  if [[ "$WARNINGS" -gt 0 ]]; then exit 1; fi
  exit 0
fi

# Human summary
python3 - "$JSON_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"workflow: {d['workflow_mode']}  branch: {d['branch']}  @{d['head'][:7]}")
if d.get("dirty"):
    print("  dirty working tree")
for b in d.get("blockers", []):
    print(f"  BLOCKER [{b['kind']}]: {b['detail']}")
for w in d.get("warnings", []):
    print(f"  warn [{w['kind']}]: {w['detail']}")
print(f"  artifacts: .rabbit-loop/preflight.html")
PY

read -r BLOCKERS WARNINGS < <(_read_preflight_counts "$JSON_FILE")

# macOS: open HTML for visual review (best-effort).
if [[ -f "$HTML_FILE" ]] && command -v open >/dev/null 2>&1; then
  open "$HTML_FILE" 2>/dev/null || true
fi

if [[ "$BLOCKERS" -gt 0 ]]; then exit 2; fi
if [[ "$WARNINGS" -gt 0 ]]; then exit 1; fi
exit 0
