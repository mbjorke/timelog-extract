# Incident: observed cache overwrite degraded closed-month records

## Date

- 2026-07-01

## Summary

- `core/observed_cache.py::write_observed_summary` **overwrites** (does not merge) the observed
  cache rows for every month a report covers.
- Because gittan's collectors have limited retention, observed hours for older months **decay**
  over time. Running a report on a closed month therefore silently **lowers** that month's cached
  observed hours to reflect the now-reduced evidence.
- During a config-trim safety verification, ~8 `gittan report` runs (a June baseline plus a
  four-month Mar–Jun before/after diff) rewrote `~/.gittan/observed/2026-03.jsonl` and
  `2026-04.jsonl` with current (decayed) values. All rows now carry `captured_at: 2026-07-01`,
  confirming the earlier, higher captures were discarded. No observed-cache backup existed, so the
  prior values are unrecoverable.

## Impact

- **Invoiced records: NOT affected.** The authoritative source for closed months is
  `~/.gittan/invoice/invoiced/ledger.yaml` ("AUTHORITATIVE — vad som faktiskt skickats i Briox").
  It is intact (e.g. `ass-membra-2026-03` = 18.75 h). The observed cache is a statusline
  convenience (`observed − handled`), not invoiced truth.
- **Observed (raw) cache for closed months Mar/Apr** was lowered to current-evidence values;
  earlier higher captures lost.
- The ledger already documented that gittan-tracked ÅSS March was below the invoiced 18.75 h at
  invoice time (untracked SFTP/wp-admin/meetings), so the raw observed figure being low for those
  months is expected — the incident is the *silent downward rewrite*, not the low number itself.

## Not the cause

- The **config trim** (removal of 31 zero-hit noise rules) was verified zero-impact: a per-line
  before/after comparison (pre-trim backup config vs trimmed config) was **identical for Mar, Apr,
  May, Jun**, and the trim touched none of the invoiced projects (`ÅSS: Nav` / `ÅSS: Membra`).

## Root cause

- `write_observed_summary` treats each run as authoritative for the months it covers and replaces
  those months' rows wholesale. With decaying evidence, a later run stores strictly less, and there
  is no high-water-mark protection and no backup.

## Contributing action

- Running reports on **closed** months (as part of trim verification) triggered the overwrite. The
  verification that proved the trim safe is what degraded the observed cache.

## Resolution

- `write_observed_summary` now performs a **keep-max merge** per `(project, date)`: a report run can
  only raise or hold a stored observed value, never lower it. Evidence decay can no longer degrade
  the record. Existing `(project, date)` rows absent from a later run are preserved.
- Regression test in `tests/test_observed_cache.py` covering the lower-rewrite and missing-key cases.

## Prevention

- **Keep-max is monotonic** — the mechanical guarantee that a report can never degrade the observed
  cache again.
- Docstring in `core/observed_cache.py` and a note in `AGENTS.md` (Local data safety) state: closed-
  month reports are safe (keep-max); for closed months the **ledger** is authoritative, not a fresh
  report.
- Caveat documented: keep-max can leave a stale row if a `(project, date)` is later re-attributed to
  a different project; the observed cache is a high-water mark, not a live truth. Reconcile against
  the ledger / `reported/` for closed months.
- Follow-up (not in this fix): consider a timestamped backup of `~/.gittan/observed/` before writes,
  mirroring the projects-config backup pattern.
