"""Shell script body for the global post-commit timelog hook."""

from textwrap import dedent

# The embedded resolver must sit at column 0 in the final script (Python is
# indentation-sensitive), so it lives outside the dedented shell template and
# is substituted in afterwards. Keeping column-0 lines inside the template
# would defeat dedent() and leave the shebang indented — a broken shebang
# means git runs the hook under sh, where zsh's ${VAR:A} aborts the script.
_RESOLVER_PY = """\
import json, os, re, sys

home = os.path.expanduser("~")
cfg = os.environ.get("GITTAN_PROJECTS_CONFIG") or os.path.join(home, ".gittan", "timelog_projects.json")
repo = os.environ.get("GITTAN_HOOK_REPO", "")


def norm(value):
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


try:
    with open(cfg, encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, ValueError):
    sys.exit(0)

profiles = data.get("projects", data) if isinstance(data, dict) else data
if not isinstance(profiles, list):
    sys.exit(0)

project_id = repo
worklog_path = None
target = norm(repo)
for profile in profiles:
    if not isinstance(profile, dict):
        continue
    # Mirror the main config loader: project_id defaults to name.
    identity = profile.get("project_id") or profile.get("name")
    if not identity:
        continue
    names = [identity, profile.get("name"), profile.get("canonical_project")]
    names.extend(profile.get("aliases") or [])
    if target and target in {norm(n) for n in names if n}:
        project_id = identity
        worklog = profile.get("worklog")
        if worklog:
            path = os.path.expanduser(worklog)
            if not os.path.isabs(path):
                # Relative worklogs resolve against the config directory,
                # matching core/config.py, not the repo cwd.
                path = os.path.join(os.path.dirname(cfg), path)
            worklog_path = path
        else:
            worklog_path = os.path.join(home, ".gittan", "worklogs", identity + ".md")
        break

if worklog_path:
    print(worklog_path)

try:
    shadow_log_state = str(data.get("shadow_log", "off")).strip().lower()
    if shadow_log_state == "on":
        subject = os.environ.get("GITTAN_HOOK_SUBJECT", "").strip()
        branch = os.environ.get("GITTAN_HOOK_BRANCH", "").strip()
        commit_hash = os.environ.get("GITTAN_HOOK_HASH", "").strip()
        if subject:
            from datetime import datetime, timezone
            from pathlib import Path
            event = {
                "source": "git-commit",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": f"[{repo}:{branch}] {subject}" if branch else f"[{repo}] {subject}",
                "project": project_id,
                "source_provenance": {
                    "repo": repo,
                    "branch": branch,
                    "subject": subject,
                    "commit": commit_hash,
                }
            }
            try:
                from core.evidence_store import capture_events
                capture_events([event], home=Path(home))
            except Exception as exc:
                err_file = Path(home) / ".gittan" / "capture-errors.jsonl"
                try:
                    err_file.parent.mkdir(parents=True, exist_ok=True)
                    with err_file.open("a", encoding="utf-8") as ef:
                        ef.write(json.dumps({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "error": str(exc),
                            "source": "git-commit",
                        }, ensure_ascii=False) + "\\n")
                except Exception:
                    pass
except Exception:
    pass
"""

HOOK_BODY = dedent(
    """\
    #!/usr/bin/env zsh
    # managed-by-gittan: global-timelog
    set -euo pipefail

    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
    ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "${ROOT_DIR:-}" ]] || exit 0

    GITTAN_CFG_DIR="$HOME/.gittan"
    SCOPE_FILE="$GITTAN_CFG_DIR/timelog_repos.txt"
    FILENAME_FILE="$GITTAN_CFG_DIR/timelog_filename"
    TIMELOG_NAME="TIMELOG.md"
    CONFIGURED_CANDIDATE=""
    if [[ -f "$FILENAME_FILE" ]]; then
      CANDIDATE="$(head -n 1 "$FILENAME_FILE" 2>/dev/null | tr -d '\\r')"
      if [[ -n "${CANDIDATE:-}" ]]; then
        case "$CANDIDATE" in
          ..|*../*|*/..|../*|*/../*)
            echo "gittan-hook: refusing unsafe .. segments in timelog_filename" >&2
            CANDIDATE=""
            ;;
        esac
      fi
      if [[ -n "${CANDIDATE:-}" ]]; then
        CONFIGURED_CANDIDATE="$CANDIDATE"
        TIMELOG_NAME="$CANDIDATE"
      fi
    fi
    if [[ -f "$SCOPE_FILE" ]]; then
      if ! grep -Fxq -- "$ROOT_DIR" "$SCOPE_FILE" 2>/dev/null; then
        exit 0
      fi
    fi

    if [[ "$TIMELOG_NAME" == /* ]]; then
      TIMELOG_FILE="$TIMELOG_NAME"
    elif [[ "$TIMELOG_NAME" == ~/* ]]; then
      TIMELOG_FILE="$HOME/${TIMELOG_NAME#~/}"
    else
      TIMELOG_FILE="$ROOT_DIR/$TIMELOG_NAME"
    fi
    home_canon="${HOME:A}"
    root_canon="${ROOT_DIR:A}"
    REPO_BASENAME="${ROOT_DIR##*/}"
    # Resolve the central worklog from timelog_projects.json, which owns
    # project identity. Path-derived ids were tried before and are wrong here:
    # worktrees and moved repos change the path, so the same project silently
    # split across several files. project_id is stable; the path is not.
    GITTAN_HOOK_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    GITTAN_HOOK_HASH="$(git rev-parse HEAD 2>/dev/null || true)"
    SUBJECT="$(git log -1 --pretty=%s)"
    PROJECT_WORKLOG="$(GITTAN_HOOK_REPO="$REPO_BASENAME" GITTAN_HOOK_BRANCH="$GITTAN_HOOK_BRANCH" GITTAN_HOOK_SUBJECT="$SUBJECT" GITTAN_HOOK_HASH="$GITTAN_HOOK_HASH" python3 -c '
    @RESOLVER_PY@' 2>/dev/null || true)"
    if [[ -z "${PROJECT_WORKLOG:-}" ]]; then
      # Unknown repo: still central, still no hash — a plain name a human can
      # recognise and later attach to a profile.
      PROJECT_WORKLOG="$HOME/.gittan/worklogs/${REPO_BASENAME}.md"
    fi
    if [[ -z "${CONFIGURED_CANDIDATE:-}" || "$CONFIGURED_CANDIDATE" == "TIMELOG.md" ]]; then
      # Note: no [[ -f ]] guard. Requiring the file to pre-exist is what made
      # commits fall back to the deprecated repo-local TIMELOG.md; the append
      # below creates it when missing.
      TIMELOG_FILE="$PROJECT_WORKLOG"
    fi
    canon="${TIMELOG_FILE:A}"
    if [[ "$canon" != "$home_canon"/* && "$canon" != "$root_canon"/* ]]; then
      echo "gittan-hook: refusing timelog path outside home directory or repo root" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$TIMELOG_FILE")"
    TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"

    if [[ ! -f "$TIMELOG_FILE" ]]; then
      {
        echo "# TIMELOG"
        echo
      } > "$TIMELOG_FILE"
    fi

    {
      echo "## $TIMESTAMP"
      echo "- Commit: $SUBJECT"
      echo
    } >> "$TIMELOG_FILE"
    """
).replace("@RESOLVER_PY@", _RESOLVER_PY)

assert HOOK_BODY.startswith("#!"), "hook shebang must be at byte 0"
