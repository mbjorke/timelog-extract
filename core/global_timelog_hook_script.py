"""Shell script body for the global post-commit timelog hook."""

from textwrap import dedent

# The embedded resolver must sit at column 0 in the final script (Python is
# indentation-sensitive), so it lives outside the dedented shell template and
# is substituted in afterwards. Keeping column-0 lines inside the template
# would defeat dedent() and leave the shebang indented — a broken shebang
# means git runs the hook under sh, where zsh's ${VAR:A} aborts the script.
_RESOLVER_PY = """\
import hashlib, json, os, re, sys

home = os.path.expanduser("~")
# One state root, matching core/evidence_store.py::spool_dir(): $GITTAN_HOME
# *is* the data dir when set. Writing to $HOME/.gittan while capture_events()
# drains $GITTAN_HOME left the event permanently undrained.
_env_root = (os.environ.get("GITTAN_HOME") or "").strip()
state_root = os.path.expanduser(_env_root) if _env_root else os.path.join(home, ".gittan")
cfg = os.environ.get("GITTAN_PROJECTS_CONFIG") or os.path.join(state_root, "timelog_projects.json")
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
            worklog_path = os.path.join(state_root, "worklogs", identity + ".md")
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
                spool_dir = Path(state_root) / "spool"
                spool_dir.mkdir(parents=True, exist_ok=True)
                name_part = commit_hash if commit_hash else datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
                # Scope the name by repo, not by pid. Two repositories can in
                # principle produce the same commit hash — byte-identical commit
                # objects, e.g. two empty initial commits made in the same second
                # by the same author — and then one os.replace() would silently
                # overwrite the other event. Repo is the axis that actually
                # separates them.
                #
                # Deliberately NOT a pid or random suffix: the hash in the name is
                # what makes re-spooling the same commit idempotent. Uniquifying
                # per run would instead write two files whose events carry
                # different `timestamp` values, and since the dedup fingerprint is
                # (source, observed_at, detail), they would survive as two records
                # for one commit.
                # norm() alone is lossy — "repo-a" and "repo_a" collapse to the
                # same slug, so a shared commit hash would still overwrite. The
                # digest mirrors _device_slug() in core/evidence_store.py; the
                # readable stem is kept for humans.
                #
                # The digest is over the absolute repo path, not its basename:
                # ~/work/api and ~/personal/api are different repositories with
                # the same name, and hashing the name alone leaves them sharing
                # one spool file. Path here is a transient queue key only — it
                # must not reach the worklog filename, where a path-derived id
                # splits one project across worktrees and moved checkouts
                # (tests/test_global_timelog_hook_script.py::
                # test_never_derives_worklog_name_from_path_hash).
                repo_stem = norm(repo) or "unknown-repo"
                repo_key = os.environ.get("GITTAN_HOOK_REPO_PATH", "") or repo or ""
                repo_digest = hashlib.sha256(repo_key.encode("utf-8")).hexdigest()[:12]
                repo_part = f"{repo_stem}-{repo_digest}"
                spool_file = spool_dir / f"commit-{repo_part}-{name_part}.json"
                # Publish atomically: the drainer globs "*.json" and unlinks
                # anything it cannot parse, so a half-written file is a silently
                # lost commit event. The temp name ends in .tmp, outside that glob.
                temp_file = spool_file.with_suffix(f".{os.getpid()}.tmp")
                with temp_file.open("w", encoding="utf-8") as sf:
                    json.dump(event, sf, ensure_ascii=False)
                os.replace(temp_file, spool_file)
            except Exception as exc:
                err_file = Path(state_root) / "capture-errors.jsonl"
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

    # Gittan's own data directory is not a project, and a commit there is
    # bookkeeping rather than work. The autocommit runbook makes that directory a
    # git repo, so without this guard every auto-commit fires this hook, which
    # spools an event and appends a worklog *inside* the same directory, which the
    # next tick commits, which fires the hook again. It never settles, and every
    # cycle fabricates a worklog entry attributed as activity (GH-535).
    #
    # GITTAN_HOME is honoured because the rest of the code already treats it as the
    # data dir; canonical paths so a symlinked home still matches.
    #
    # Normalize exactly as core/config.py::gittan_data_dir() does — strip
    # surrounding whitespace, then expand a leading ~ — because the embedded
    # Python resolver below already does, and reading the raw value here made one
    # variable name mean two directories inside a single hook run. A literal
    # "~/dir" is a *relative* path, so the scope file simply went missing and the
    # allowlist failed open (logging every repo) instead of failing loudly.
    GITTAN_DATA_DIR="${GITTAN_HOME:-}"
    GITTAN_DATA_DIR="${GITTAN_DATA_DIR#"${GITTAN_DATA_DIR%%[![:space:]]*}"}"
    GITTAN_DATA_DIR="${GITTAN_DATA_DIR%"${GITTAN_DATA_DIR##*[![:space:]]}"}"
    case "$GITTAN_DATA_DIR" in
      "~")   GITTAN_DATA_DIR="$HOME" ;;
      "~/"*) GITTAN_DATA_DIR="$HOME/${GITTAN_DATA_DIR#"~/"}" ;;
      "~"*)
        # ~user: expand in a subshell, because zsh aborts on an unknown user and
        # a commit hook must not die over its own config. expanduser() leaves an
        # unresolvable user untouched, so falling through matches Python.
        _gittan_expanded="$(GITTAN_TILDE="$GITTAN_DATA_DIR" zsh -c 'E=${~GITTAN_TILDE}; print -r -- $E' 2>/dev/null || true)"
        if [[ -n "${_gittan_expanded:-}" ]]; then
          GITTAN_DATA_DIR="$_gittan_expanded"
        fi
        ;;
    esac
    # Whitespace-only is empty after the trim, which is why this replaces the
    # ${VAR:-default} that used to sit on the assignment above.
    [[ -n "${GITTAN_DATA_DIR:-}" ]] || GITTAN_DATA_DIR="$HOME/.gittan"
    # Must be absolute, matching core/config.py::gittan_data_dir(), which raises
    # on anything else. A relative value resolves against the *repo* here and
    # against the CLI's cwd there, so the two would never meet. Warn and stop
    # rather than append this commit to a path nobody will look in — and note
    # this is the only check the shell needs, so it cannot drift from Python the
    # way whitespace and ~ handling did.
    if [[ "$GITTAN_DATA_DIR" != /* ]]; then
      echo "gittan-hook: GITTAN_HOME must be an absolute path, got '$GITTAN_DATA_DIR'; skipping" >&2
      exit 0
    fi
    gittan_data_canon="${GITTAN_DATA_DIR:A}"
    root_dir_canon="${ROOT_DIR:A}"
    if [[ "$root_dir_canon" == "$gittan_data_canon" || "$root_dir_canon" == "$gittan_data_canon"/* ]]; then
      exit 0
    fi

    # A repository under a temporary directory is a test fixture, not work.
    # A test suite creates throwaway repos and commits in them; with this hook
    # installed globally, every one of those commits was recorded as evidence.
    # On a developer machine that can dominate the git-commit source entirely.
    # The commits are real, the work is not, and hash-chained evidence is the
    # wrong place to learn that difference afterwards.
    #
    # Placed *after* the GITTAN_HOME validation on purpose: a misconfigured data
    # dir is something the operator must hear about from any repository, and an
    # earlier version of this guard swallowed that warning by exiting first.
    #
    # Escape hatch, because this is the hook deciding what counts as work and
    # that decision should belong to the person whose hours they are.
    if [[ "${GITTAN_HOOK_ALLOW_TEMP:-0}" != "1" ]]; then
      for _tmp_root in "${TMPDIR:-}" /tmp /var/folders /private/tmp /private/var/folders; do
        [[ -n "$_tmp_root" ]] || continue
        _tmp_canon="${_tmp_root:A}"
        if [[ "$root_dir_canon" == "$_tmp_canon" || "$root_dir_canon" == "$_tmp_canon"/* ]]; then
          exit 0
        fi
      done
    fi

    # One data dir for the whole hook: scope file, filename override and the
    # unknown-repo worklog fallback all live under $GITTAN_DATA_DIR (GH-549).
    # Splitting them across $HOME/.gittan meant a run with $GITTAN_HOME set read
    # its scope from one root and wrote the worklog into another.
    GITTAN_CFG_DIR="$GITTAN_DATA_DIR"
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
    PROJECT_WORKLOG="$(GITTAN_HOOK_REPO="$REPO_BASENAME" GITTAN_HOOK_REPO_PATH="$ROOT_DIR" GITTAN_HOOK_BRANCH="$GITTAN_HOOK_BRANCH" GITTAN_HOOK_SUBJECT="$SUBJECT" GITTAN_HOOK_HASH="$GITTAN_HOOK_HASH" python3 -c '
    @RESOLVER_PY@' 2>/dev/null || true)"
    if [[ -z "${PROJECT_WORKLOG:-}" ]]; then
      # Unknown repo: still central, still no hash — a plain name a human can
      # recognise and later attach to a profile.
      PROJECT_WORKLOG="$GITTAN_DATA_DIR/worklogs/${REPO_BASENAME}.md"
    fi
    if [[ -z "${CONFIGURED_CANDIDATE:-}" || "$CONFIGURED_CANDIDATE" == "TIMELOG.md" ]]; then
      # Note: no [[ -f ]] guard. Requiring the file to pre-exist is what made
      # commits fall back to the deprecated repo-local TIMELOG.md; the append
      # below creates it when missing.
      TIMELOG_FILE="$PROJECT_WORKLOG"
    fi
    canon="${TIMELOG_FILE:A}"
    # The data dir is a third allowed root: $GITTAN_HOME may point outside $HOME
    # (a sandbox, an external volume), and the central worklog lives there.
    if [[ "$canon" != "$home_canon"/* && "$canon" != "$root_canon"/* && "$canon" != "$gittan_data_canon"/* ]]; then
      echo "gittan-hook: refusing timelog path outside home directory, repo root, or Gittan data directory" >&2
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
