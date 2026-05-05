# GitLab / non-GitHub Git hosts — future API collector (epic stub)

**Status:** Not implemented. The GitHub collector is the only first-party **Git-host REST** integration today.

## Problem

Some teams use **GitLab** (SaaS or self-managed), **Azure DevOps**, or other hosts. Browser and IDE sources already capture *local* and *web* activity; a dedicated API collector would mirror the GitHub source pattern (authenticated timeline / activity) for those platforms.

## Likely MVP shape (for a future spec)

- **Configuration:** host base URL + API token via **environment variables** (same hygiene as `GITHUB_TOKEN` / `GITHUB_API_BASE_URL`), not secrets in `timelog_projects.json`.
- **Scope:** narrow first slice (e.g. user or project events with a clear rate-limit story).
- **Tests:** mocked HTTP, parity with `collector_status` / doctor visibility.

## Until then

Use Chrome + `match_terms`, triage domain hints, IDE sources, and TIMELOG for evidence on non-GitHub hosts. See [multi-account-git-sources.md](multi-account-git-sources.md) for GitHub-specific multi-login and Enterprise Server settings.
