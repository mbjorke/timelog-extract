# Multiple Git accounts and GitHub API hosts

Gittan’s **GitHub source** reads the public events API (`/users/{login}/events/public`). This runbook explains how to combine **several GitHub identities** in one report and how to point the client at **GitHub Enterprise Server** instead of github.com.

## Several GitHub logins (same API host)

Use a **comma-separated** list:

- **Environment:** `GITHUB_USER=workuser,personaluser` (or `GITHUB_LOGIN` with the same shape).
- **CLI:** `--github-user workuser,personaluser`

Each login is queried separately; overlapping events are **deduplicated** by GitHub’s event id. One `GITHUB_TOKEN` is usually enough for authenticated requests and rate limits (the token identifies the API client; the URL path selects whose public events are listed).

**Limits:** GitHub only retains roughly the **300 most recent** public events per user; older ranges stay sparse.

## GitHub Enterprise Server (custom hostname)

If the company uses **`https://git.example.com`** (or similar) instead of `github.com`, set the REST root explicitly:

- **`GITHUB_API_BASE_URL`** — e.g. `https://git.example.com/api/v3` (no trailing slash required; Gittan normalizes it).

Use a **personal access token issued on that instance** in `GITHUB_TOKEN`, not a token from github.com.

**SSO / SAML:** If the org requires SSO authorization for tokens, authorize the PAT in the GitHub (Enterprise) UI the same way you would for github.com SaaS.

## When the Git host is not GitHub at all

GitLab, Azure DevOps, Gitea, etc. are **not** covered by the GitHub collector. Activity there often still appears via **Chrome** (web UI), **IDE logs** (local clones), and **TIMELOG** entries. Use `match_terms` / triage domain mapping in `timelog_projects.json` to classify that traffic.

See [gitlab-self-hosted-future.md](gitlab-self-hosted-future.md) for a planned direction on non-GitHub APIs.

## Related

- [sources-and-flags.md](../sources/sources-and-flags.md) — how sources merge into one timeline.
- [manual-test-matrix-0-2-x.md](manual-test-matrix-0-2-x.md) — GitHub manual checks.
