# Manual test matrix — 0.2.x

Use this when validating **Gittan / timelog-extract** after install or before a patch release. Record **expected vs actual** in the tables; attach notes if something is unclear (permissions, empty sources, etc.).

**Environment (fill in):**

| Field | Value |
|-------|--------|
| Date | |
| OS / arch | |
| Python version | |
| Package | `pip install -e .` / wheel version / git SHA |
| `gittan -V` output | |

---

## Preconditions

- [ ] `bash scripts/run_autotests.sh` passes locally (CI parity).
- [ ] You know a **date range** you can sanity-check (meetings, commits, browser habits).

---

## Deterministic spot-check (seeded worklog, optional)

Use this when you want **repeatable pass/fail signals** independent of Chrome/Mail. It relies only on **`TIMELOG.md`-style** parsing and a **fixed local date range**.

**1. Save a temporary worklog** (e.g. `manual_qa_worklog.md`) with **six** dated lines in a two-day window (Markdown headings + one bullet of text each). Example content (adjust dates if your locale requires different days; keep the **strings** `example.com/foo` and `Test Project`):

```markdown
## 2024-01-01 09:00
- Client review https://example.com/foo Test Project

## 2024-01-01 10:15
- Follow-up https://example.com/foo docs

## 2024-01-01 11:00
- Test Project standup notes

## 2024-01-01 14:00
- Deep work Test Project

## 2024-01-02 09:30
- https://example.com/foo regression check

## 2024-01-02 15:00
- Wrap-up Test Project
```

**2. Commands** (no `timelog_projects.json`, or keep it away from this run; use `--worklog` explicitly). Use **`--keywords`** so snippets match the fallback profile — otherwise events may stay **Uncategorized** and be **dropped** from default reports and from **`totals.event_count`** in JSON.

| Step | Command | Pass criteria (check JSON with `--format json` where noted) |
|------|---------|---------------------------------------------------------------|
| D1 | `gittan doctor` | Process exits 0; table renders (paths may show missing files on a clean machine — note in Pass / notes). |
| D2 | `gittan report --from 2024-01-01 --to 2024-01-02 --worklog ./manual_qa_worklog.md --worklog-format md --keywords "test,example,foo"` | **≥ 5** events counted toward the report (terminal summary or JSON); TIMELOG source appears in **Source Summary** when using `--source-summary`. |
| D3 | Same as D2 plus `--include-uncategorized` (optional cross-check) | **≥ 1** session across days in the JSON/tables when gap/min-session rules allow grouping (if zero sessions, increase `gap_minutes` temporarily or confirm events are in range). |
| D4 | Same as D2 + `--format json` | Payload `schema` is `timelog_extract.truth_payload`; `version` key present; **`totals.event_count` ≥ 5**; at least one serialized event has **`detail`** containing **`example.com/foo`** OR **`Test Project`** (search in `days[].sessions[].events` or equivalent). |

**3. Note on “UTC”:** CLI dates are **local calendar days**; the JSON payload’s `range` uses **ISO timestamps** (see output). Match the **same calendar dates** you put in the worklog file.

---

## Scenario A — No project config file

**Setup:** Rename or move aside `timelog_projects.json` (or run from a directory where it does not exist). Use default CLI (no extra flags first). For **objective** thresholds, run the **Deterministic spot-check** above in parallel.

| Step | Command / action | Expected (rough) | Pass / notes |
|------|-------------------|------------------|--------------|
| A1 | `gittan doctor` | Completes; project file may show missing or readable depending on path | |
| A2 | `gittan report --today` (or small date range) | Single fallback profile (`default-project`); **Chrome** may contribute **few or no** visits unless URLs/titles contain that string | |
| A3 | Same with `--include-uncategorized` | You see how much lands in **Uncategorized** vs a named project | |
| A4 | `gittan report --today --format json` | Valid payload; `schema` / `version` present; scan `events` / `sessions` | |

**What to write down:** Total hours feel plausible? Is the report **too empty** because Chrome pre-filter is narrow? Any warnings on stdout?

---

## Scenario B — No config file, meaningful CLI overrides

**Setup:** Still no `timelog_projects.json`.

| Step | Command / action | Expected (rough) | Pass / notes |
|------|-------------------|------------------|--------------|
| B1 | `gittan report --today --project "YourName" --keywords "acme,repo,jira"` (adjust to strings you **actually** have in URLs/titles/logs) | More **Chrome** rows collected; more events may classify to **one** project bucket | |
| B2 | Compare totals / Uncategorized vs Scenario A | Should move toward **less Uncategorized** if keywords match reality | |

---

## Scenario C — Minimal `timelog_projects.json`

**Setup:** Restore or create a **small** config (e.g. two projects with explicit `match_terms`). See `timelog_projects.example.json` in the repo.

| Step | Command / action | Expected (rough) | Pass / notes |
|------|-------------------|------------------|--------------|
| C1 | `gittan doctor` | Project config **found** under repo root (or path you use) | |
| C2 | `gittan report` for same range as A/B | Events distributed across **multiple** projects; `classify_project` scoring visible in practice | |
| C3 | Optional: `--only-project` / `--customer` if you use those fields | Filters match your JSON | |

---

## Optional — HTML / PDF / narrative

| Step | Command | Pass / notes |
|------|---------|--------------|
| O1 | `--report-html` path | Single file opens; payload embedded / readable |
| O2 | `--pdf` (if used) | Invoice PDF generates; labels English as documented |
| O3 | `--narrative` | Short English summary after report; no crash |

---

## Optional — GitHub source

| Step | Command | Pass / notes |
|------|---------|--------------|
| G1 | With `GITHUB_USER` or `--github-user`, `--github-source on`, range where you had public activity | Events appear; sparse for **old** ranges (API window ~300 recent events) |

---

## Sign-off

| Question | Answer |
|----------|--------|
| Blockers for patch release? | |
| Follow-up issues filed? | |

---

## Reference (why Scenario A can look “empty”)

- Without a config file, the engine uses a **fallback profile** from `--project` (default `default-project`) and `--keywords`.
- **Chrome** only **imports** history rows whose URL/title matches **any** keyword derived from profiles — a very narrow default string yields **few** visits.
- Default reports **exclude** Uncategorized unless `--include-uncategorized` — totals can look low if most events are uncategorized.

See `core/config.py` (`load_profiles`), `collectors/chrome.py` (keyword filter), `core/domain.py` (`classify_project`).
