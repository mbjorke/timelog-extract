# CLI-First v1 Release Checklist

This checklist is the default v1 launch gate for Timelog Extract.
It assumes CLI and script workflows are the primary user path, while the Cursor extension remains optional/beta.

## Execution Snapshot (2026-04-10)

- Local tests: `python3 -m unittest discover -s tests -p "test_*.py"` ✅
- Editable install: `python3 -m pip install -e .` ✅
- CLI-first smoke: `python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json` ✅
- JSON contract: `python3 timelog_extract.py --today --format json` includes `schema` and `version` ✅
- Empty-range PDF: `python3 timelog_extract.py --from 1999-01-01 --to 1999-01-02 --invoice-pdf` ✅
- Source summary readability: `python3 timelog_extract.py --today --source-summary` ✅

## 1) Product Scope Lock

- [x] Confirm v1 scope is CLI-first (engine + reports + PDF + JSON/HTML exports).
- [x] Keep extension labeled as scaffold/beta (not required for core usage).
- [ ] Freeze new source additions until after v1 tag.
- [ ] Freeze non-critical refactors that do not reduce release risk.

## 2) Must-Pass Quality Gates

- [x] `python3 -m unittest discover -s tests -p "test_*.py"` passes locally.
- [ ] CI `python` workflow is green on release candidate commit.
- [x] `scripts/run_engine_report.py --today --pdf` works on clean clone + fresh env.
- [x] `timelog_extract.py --today --format json` outputs valid truth payload (`schema`, `version` present).
- [x] PDF generation works for both non-empty and empty ranges.

## 3) Installation + Onboarding

- [x] README has one "use it now" command that succeeds on first try.
- [ ] Install instructions are tested in a clean Python 3.9+ environment.
- [x] Worklog path/default behavior is explicitly documented and accurate.
- [x] Troubleshooting section includes 3 common failures:
  - missing Python deps
  - missing config path
  - file permission/path issues

## 4) Output Contract Stability

- [x] `core.engine_api.run_report_payload(...)` is treated as stable contract.
- [x] Truth payload schema/version is documented in code/docs.
- [x] Boundary tests assert `schema`, `version`, and totals block.
- [ ] Any payload key changes are release-noted before tagging.

## 5) Privacy + Trust Copy

- [x] "Local-only processing" statement appears in README and release notes.
- [x] Privacy-sensitive sources are clearly called out (Mail/Chrome/Screen Time).
- [x] No cloud upload path implied in v1 docs or examples.
- [x] Consent/toggle UX is marked as extension-beta work, not v1 blocker.

## 6) Release Artifacts

- [x] `CHANGELOG.md` has a clear v1 section (why this release matters).
- [x] Tag annotation draft is prepared (`v1.0.0` notes).
- [x] Example commands in README are copy-paste verified.
- [x] One sample output path exists in docs (`output/latest-payload.json`, PDF path example).

## 7) Smoke Test Runbook (Release Day)

- [ ] Fresh clone.
- [x] `python3 -m pip install -e .`
- [x] `python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json`
- [x] Verify:
  - `schema: timelog_extract.truth_payload`
  - `version: 1`
  - `totals` printed
  - PDF path printed and file exists
- [x] `python3 timelog_extract.py --today --source-summary` output is readable and non-erroring.

Use `docs/RC_TEST_SCRIPT_CLI_FIRST.md` for second-tester execution and report collection.

## 8) Go / No-Go Decision

Release is **GO** only if all conditions hold:

- [ ] All quality gates pass.
- [ ] No open P0/P1 defects for CLI-first path.
- [ ] Documentation reflects current behavior (no stale commands/settings).
- [ ] At least one full smoke test completed by someone other than implementer.

If any fail, release is **NO-GO** and tag is postponed.

## 9) Post-Release (first 7 days)

- [ ] Track top 5 user friction points from pilot usage.
- [ ] Triage parser failures by source and add fixture tests for highest-frequency breakages.
- [ ] Decide extension roadmap timing after CLI-first signal is validated.

