# Jira worklog sync

Use `jira-sync` to post TIMELOG-derived time into Jira issue worklogs.

## Prerequisites

Set these environment variables (or pass matching CLI options):

- `JIRA_BASE_URL` (example: `https://your-org.atlassian.net`)
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

Issue key mapping follows this order:

1. Jira key from commit messages in the relevant session window (`ABC-123`).
2. Jira key from current branch name.
3. If neither is found, the session is skipped as unresolved.

## Command examples

Dry run preview:

`gittan jira-sync --last-week --dry-run`

Real posting with confirmation per candidate:

`gittan jira-sync --last-week --require-confirm`

Custom git repository for ticket lookup:

`gittan jira-sync --today --git-repo /path/to/repo`

## Behavior

- Time is aggregated into one Jira worklog per `issue + day`.
- The command prompts for each candidate unless `--require-confirm` is disabled.
- Summary output reports posted, skipped, unresolved, and failed candidates.
