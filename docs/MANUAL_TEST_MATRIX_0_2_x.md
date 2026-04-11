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

## Scenario A — No project config file

**Setup:** Rename or move aside `timelog_projects.json` (or run from a directory where it does not exist). Use default CLI (no extra flags first).

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
