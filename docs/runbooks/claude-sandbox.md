# Claude Code Bash sandbox for this repo

`.claude/settings.json` (checked in) enables Claude Code's sandboxed Bash tool
for anyone working on this repo, so most shell commands run without permission
prompts while the OS enforces filesystem and network boundaries. Reference:
[Configure the sandboxed Bash tool](https://code.claude.com/docs/en/sandbox).

## What the policy allows and protects

### Filesystem

Sandboxed commands can write to the repo working directory and the session
temp directory by default. On top of that:

- **`allowWrite`** — `~/.gittan` so sandboxed `gittan report` runs can update
  the observed cache and evidence store (`~/.gittan/evidence/`), plus the npm
  and pip cache directories so `npm install` (cursor-extension) and
  `pip install -e .` work inside the sandbox.
- **`denyWrite`** — the critical local timelog data that agents must never
  modify or delete (see `AGENTS.md` / `CLAUDE.md` timelog file rules):
  repo-root `timelog_projects.json`, `TIMELOG.md`, `private/`, and the
  canonical `~/.gittan/timelog_projects.json`. The last one is a narrower deny
  inside the `~/.gittan` allow — the more specific rule wins, so the config
  stays protected while the rest of `~/.gittan` remains writable.
- **`credentials.files` (deny)** — `~/.ssh` and `~/.aws/credentials` are
  unreadable inside the sandbox. The sandbox's default read policy allows the
  whole disk, so these need an explicit deny. Consequence: `git push` over SSH
  fails inside the sandbox and falls back to the regular permission prompt,
  which is the intended behavior — pushes stay human-gated.

### Network

Pre-allowed domains cover the package registries and GitHub (git-over-HTTPS,
release downloads): `pypi.org`, `files.pythonhosted.org`,
`registry.npmjs.org`, `github.com`, `api.github.com`, `codeload.github.com`,
`objects.githubusercontent.com`. Anything else prompts on first use per
session. Note the documented caveat: allowing `github.com` is a potential
exfiltration path since the proxy doesn't inspect TLS — acceptable for this
local-first repo, revisit if the threat model changes.

### Excluded commands

`gh *` runs outside the sandbox: Go-based CLIs fail TLS verification under
macOS Seatbelt, and `gh` needs the real `GITHUB_TOKEN`/keychain auth anyway.
Unsandboxed `gh` calls go through the regular permission flow.

## Local overrides

- The `/sandbox` panel writes mode choices to `.claude/settings.local.json`,
  which stays untracked (gitignored). Personal tweaks go there; arrays merge
  across scopes, so local entries can only add, not remove, the shared denies.
- Sandboxing runs on macOS, Linux, and WSL2. Linux/WSL2 need `bubblewrap` and
  `socat` installed; if they're missing, Claude Code warns and runs
  unsandboxed (we deliberately do not set `failIfUnavailable`).

## What this does not change

- Read/Edit/Write file tools and MCP tools use the permission system, not the
  sandbox — only Bash commands and their child processes are sandboxed.
- The 500-line file policy, autotest gate, and branch rules are unaffected.
