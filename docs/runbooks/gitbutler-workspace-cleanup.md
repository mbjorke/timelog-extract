# GitButler workspace cleanup

Status: operational runbook (maintainer)

When the primary clone has accumulated **unapplied virtual branches** after merges,
abandoned spikes, or multi-agent sessions, use this runbook. Policy context:
[`docs/decisions/gitbutler-multi-editor-workflow.md`](../decisions/gitbutler-multi-editor-workflow.md).

**Scope:** GitButler metadata and workspace lanes in the primary clone (`gitbutler/workspace`).
Does not delete GitHub branches unless you run explicit `git push` / `gh` steps below.

## Critical: how `but branch delete` actually works

`but branch list` shows **applied and unapplied** lanes. **`but branch delete` only
removes applied stacks** — unapplied branches return:

```text
Error: Could not find branch: 'task/spinner-postamble-fix'
```

This is expected in GitButler CLI 0.20.x, not a typo in the branch name.

**Correct pattern** (one branch at a time; read output between steps):

```bash
but oplog snapshot -m "before branch cleanup"
but apply task/spinner-postamble-fix
but branch delete task/spinner-postamble-fix
```

You can use the branch **name** or the short CLI id from `but status -fv` (e.g. `sp`) **after**
apply. `but branch show task/foo` works for unapplied branches; delete does not.

### When apply fails

| Error | Fix |
| --- | --- |
| `conflicts with existing stack` | Keep your active branch applied; try apply+delete anyway — independent merged branches often work alongside the active stack. If not: `but unapply <active>` → apply stale → delete → `but apply <active>`. |
| `Uncommitted files would be overwritten` | Commit or stage `zz` changes to your active branch first (`but commit … --changes …`), then retry apply. |
| `Operation not permitted` | Retry outside sandbox / with full permissions; or use GitButler GUI. |

### Safety rails

1. **`but oplog snapshot`** before deleting more than one branch.
2. **Do not unapply your active task branch** unless apply+delete fails — unapplying first
   and then applying large merged branches can flood `zz` with stale diffs.
3. **Recovery:** `but oplog restore <sha>` (from `but oplog`) restores workspace + uncommitted state.
4. **Never chain** multiple `but apply` / `but branch delete` lines without checking status between.

## Phase 1 — sync integrated work

```bash
but pull --check
but pull
but branch list --all --no-check
```

`but pull` updates **applied** stacks onto `main`. It does **not** always remove unapplied
lanes whose PRs already merged — you still need Phase 3.

## Phase 2 — classify what remains

```bash
gh pr list --head <branch-name> --state all
```

| Signal | Action |
| --- | --- |
| PR **OPEN** | **Keep** |
| PR **MERGED** | **Delete** via apply-then-delete (Phase 3) |
| PR **CLOSED** (not merged), no intent to revive | **Delete** after skim of branch tip |
| No PR, **>2 weeks** stale | **Delete** unless commits are unique |
| No PR, **recent** spike | **Keep one week**, re-run |

## Phase 3 — delete one stale branch (template)

Replace `task/example` with the target branch name:

```bash
but apply task/example
but branch delete task/example
but status -fv
```

Repeat for the next branch. Leave your **active task branch applied** throughout if possible.

### Snapshot audit (2026-06-29)

Re-verify with Phase 1–2 before acting.

**Keep**

| Branch | Reason |
| --- | --- |
| `task/doctor-source-alignment` | Active task — PR #205 OPEN |
| `task/feature-inventory-generator` | PR #204 OPEN |
| `claude/triage-ux-spec` | PR #200 OPEN |

**Delete when merged** (apply → delete, one at a time)

| Branch | Merged PR |
| --- | --- |
| `task/spinner-postamble-fix` | #192 |
| `fix/zed-db-path` | #202 |
| `task/reported-per-issue` | #196 |
| `task/reported-sync-reads-confirmed` | #194 |
| `task/zed-collector` | #195 |
| `task/install-curl-path` | #193 |
| `claude/freelance-bridge-dashboard-CeFO5` | #140 |

**Likely delete** (abandoned)

| Branch | Reason |
| --- | --- |
| `task/ruff-baseline-cleanup` | PR #180 CLOSED |
| `cursor/lovable-middle-layer-docs` | ~2 months stale, no PR |
| `docs/agents-draft-vs-open-pr` | ~2 months stale, no PR |

**Review before delete**

| Branch | Notes |
| --- | --- |
| `revert-201-task/project-config-onboarding-guidance` | Confirm #201 / revert intent |
| `task/gui-tui-next-vision-note` | Vision note — keep if TUI planning active |
| `fix/remove-env-briox` | Delete if Briox env work moved elsewhere |
| `cursor/briox-api-connection` | Delete if Briox spike paused |

Inspect if unsure:

```bash
but branch show <branch-name>
git log -1 --oneline <branch-name>
git diff main...<branch-name> --stat
```

## Phase 4 — target end state

- **1 applied branch** (current task), or none between tasks after `but teardown`.
- **≤5 unapplied branches** (open PRs + optional one spike).
- `zz` has only intentional uncommitted work.

## Phase 5 — optional git remote hygiene

```bash
git branch -a | rg 'task/|fix/|claude/|cursor/'
git push origin --delete <branch-name>   # only when PR merged and remote should go
```

Do not delete remotes for open PRs (#204, #200, #205).

## Periodic cadence

- **After each merge to `main`:** `but pull --check` && `but pull`
- **When unapplied count > 8:** run this runbook
- **Before bulk delete:** `but oplog snapshot -m "pre-cleanup"`

## See also

- [`docs/decisions/gitbutler-multi-editor-workflow.md`](../decisions/gitbutler-multi-editor-workflow.md)
- [GitButler rubbing](https://docs.gitbutler.com/cli-guides/cli-tutorial/rubbing)
