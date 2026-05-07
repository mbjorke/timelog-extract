"""Shell script body for the global post-commit timelog hook."""

from textwrap import dedent

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
    REPO_ID="${ROOT_DIR##*/}"
    PROJECT_WORKLOG="$HOME/.gittan/worklogs/${REPO_ID}.md"
    if [[ -f "$PROJECT_WORKLOG" ]]; then
      if [[ -z "${CONFIGURED_CANDIDATE:-}" || "$CONFIGURED_CANDIDATE" == "TIMELOG.md" ]]; then
        TIMELOG_FILE="$PROJECT_WORKLOG"
      fi
    fi
    canon="${TIMELOG_FILE:A}"
    home_canon="${HOME:A}"
    root_canon="${ROOT_DIR:A}"
    if [[ "$canon" != "$home_canon"/* && "$canon" != "$root_canon"/* ]]; then
      echo "gittan-hook: refusing timelog path outside home directory or repo root" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$TIMELOG_FILE")"
    TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"
    SUBJECT="$(git log -1 --pretty=%s)"

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
)
