# Global Automatic Timelog for All Repositories (Legacy)

Status: Archived legacy reference.
Current recommended flow: use `gittan setup-global-timelog` (optionally with `--dry-run`).

This guide configures automatic timelog entries on every commit across all git repositories on this computer.

Prefer the interactive CLI guide if available:

```bash
gittan setup-global-timelog
```

Use `--dry-run` to preview changes before applying.

## Quickstart (5 Commands)

```bash
mkdir -p ~/.githooks
git config --global core.hooksPath ~/.githooks
cat > ~/.githooks/post-commit <<'EOF'
#!/bin/zsh
set -euo pipefail
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "${ROOT_DIR:-}" ]] || exit 0
TIMELOG_FILE="$ROOT_DIR/TIMELOG.md"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"
SUBJECT="$(git log -1 --pretty=%s)"
if [[ ! -f "$TIMELOG_FILE" ]]; then
  { echo "# TIMELOG"; echo; } > "$TIMELOG_FILE"
fi
{ echo "## $TIMESTAMP"; echo "- Commit: $SUBJECT"; echo; } >> "$TIMELOG_FILE"
EOF
chmod +x ~/.githooks/post-commit
touch ~/.gitignore_global && git config --global core.excludesFile ~/.gitignore_global && echo "TIMELOG.md" >> ~/.gitignore_global
```

Verification:

```bash
git config --global --get core.hooksPath
ls -l ~/.githooks/post-commit
```

## Goal

- Add a `TIMELOG.md` entry automatically after each commit.
- Keep `TIMELOG.md` local-only (never committed).
- Apply once, then work in all repositories without per-repo setup.

## What This Uses

- A global git hooks path via `core.hooksPath`.
- A global `post-commit` hook script.
- A global git ignore file that excludes `TIMELOG.md`.

## 1) Configure Global Hooks Directory

```bash
mkdir -p ~/.githooks
git config --global core.hooksPath ~/.githooks
```

Verify:

```bash
git config --global --get core.hooksPath
```

Expected output:

```text
~/.githooks
```

## 2) Create Global post-commit Hook

Create `~/.githooks/post-commit` with this exact content:

```bash
cat > ~/.githooks/post-commit <<'EOF'
#!/bin/zsh
set -euo pipefail

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "${ROOT_DIR:-}" ]] || exit 0

TIMELOG_FILE="$ROOT_DIR/TIMELOG.md"
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
EOF
```

Make it executable:

```bash
chmod +x ~/.githooks/post-commit
```

Verify:

```bash
ls -l ~/.githooks/post-commit
```

## 3) Ensure TIMELOG.md Is Never Committed

Set and use a global ignore file:

```bash
touch ~/.gitignore_global
git config --global core.excludesFile ~/.gitignore_global
```

Add ignore rule (if not already present):

```bash
echo "TIMELOG.md" >> ~/.gitignore_global
```

Optional verification:

```bash
git config --global --get core.excludesFile
rg "^TIMELOG\.md$" ~/.gitignore_global
```

## 4) Test in Any Repository

```bash
cd /path/to/any/repo
echo "hook test $(date '+%Y-%m-%d %H:%M:%S')" >> .hook-test.txt
git add .hook-test.txt
git commit -m "test: verify global timelog hook"
```

Check latest timelog entries:

```bash
tail -n 6 TIMELOG.md
```

Expected format:

```md
## YYYY-MM-DD HH:MM
- Commit: test: verify global timelog hook
```

## Troubleshooting

### `zsh: event not found: /bin/zsh`

Cause: You pasted hook content directly into shell instead of writing to a file.  
Fix: Use the `cat <<'EOF' ... EOF` command block above.

### Hook does not run

Check:

```bash
git config --global --get core.hooksPath
ls -l ~/.githooks/post-commit
```

- Ensure `core.hooksPath` points to `~/.githooks`.
- Ensure `post-commit` is executable.

### TIMELOG.md gets staged accidentally

Unstage only:

```bash
git restore --staged TIMELOG.md
```

Then verify:

```bash
git status --short
```

## Notes

- Git hooks are local-machine behavior; they are not shared via normal commits.
- This setup is machine-wide and affects all repositories for this user.
- If needed, each repository can still have manual timelog additions in `TIMELOG.md`.
