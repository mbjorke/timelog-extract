# Demo API on Cloudflare Workers

Status: draft runbook

## Purpose

Host the landing-page live terminal demo at `https://api.gittan.sh` without
running arbitrary shell commands or the full Python CLI.

This API is intentionally a deterministic mock. It exists so `gittan-home` can
show a live terminal interaction while preserving the product truth:

- local traces become evidence,
- classified time is a candidate,
- approved invoice time requires human review.

## Source File

Worker implementation:

- `deploy/cloudflare/demo-worker.js`

## API Contract

Health:

- `GET https://api.gittan.sh/demo/health`

Create session:

- `POST https://api.gittan.sh/demo/sessions`
- response: `{ "session_id": "..." }`

Execute command:

- `POST https://api.gittan.sh/demo/sessions/{session_id}/exec`
- request: `{ "line": "gittan doctor" }`
- success response: `text/plain`
- denied response: JSON error

Allowed commands:

- `help`
- `clear`
- `gittan doctor`
- `gittan setup`
- `gittan setup --dry-run`
- `gittan status`
- `gittan report`
- `gittan report --today --source-summary`
- `gittan report --today --format json`

No arbitrary command execution is allowed.

## Frontend Configuration

The landing page should point to:

```html
<meta name="gittan-demo-api-base" content="https://api.gittan.sh">
```

For `gittan-home`, use:

```ts
const DEMO_API_BASE = "https://api.gittan.sh";
```

## Deploy With Wrangler

### Account safety gate

Deploy this Worker only to the maintainer's **private Cloudflare account**.
Do **not** deploy it to AX Finans or any customer/work account.

Before running deploy:

1. Run `npx wrangler whoami`.
2. Confirm the active account is the private account that owns `gittan.sh`.
3. Confirm the target zone/domain is `gittan.sh`.
4. If the account name, account ID, or zone looks like AX Finans, stop.

From a machine authenticated to the correct private Cloudflare account:

```bash
npx wrangler deploy --config deploy/cloudflare/wrangler.toml
```

Then configure a Worker route or custom domain:

- hostname: `api.gittan.sh`
- route/path: `api.gittan.sh/*`
- worker: `gittan-demo-api`

## Smoke Test

After deploy:

```bash
curl https://api.gittan.sh/demo/health
curl -X POST https://api.gittan.sh/demo/sessions
```

Then use the returned `session_id`:

```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{"line":"gittan doctor"}' \
  https://api.gittan.sh/demo/sessions/<session_id>/exec
```

Expected behavior:

- `gittan doctor` prints demo environment checks.
- `gittan setup --dry-run` previews safe setup checks and makes no changes.
- `gittan setup` prints a demo-mode setup summary with no machine mutation.
- `gittan status` prints a demo-selected today summary with observed /
  classified / approved split.
- `gittan report` selects today for the demo and prints the same safe summary
  as `gittan report --today --source-summary`.
- `gittan report --today --source-summary` prints source counts and observed /
  classified / approved split.
- `gittan report --today --format json` prints the deterministic truth payload.
- unknown commands return: `Command not allowed in demo sandbox. Try: help`.

## Safety Notes

- Do not add real shell execution to this Worker.
- Do not include user data or real customer domains.
- Keep outputs deterministic so screenshots and demos stay reproducible.
- Treat this as a marketing/demo API, not the product engine.
