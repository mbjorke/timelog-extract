# RC Test Script (CLI-first v1)

Use this script for a second-person release-candidate check on a clean machine or clean environment.

## Goal

Validate that the CLI-first path works end-to-end without IDE/extension setup.

## Preconditions

- Python 3.9+ installed.
- Git installed.
- No assumptions about prior local timelog tooling.

## Steps (copy/paste)

1) Clone and enter repo:

```bash
git clone https://github.com/mbjorke/timelog-extract.git
cd timelog-extract
```

2) Install package in editable mode:

```bash
python3 -m pip install -e .
```

3) Run baseline tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

4) Run CLI-first smoke command:

```bash
python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json
```

5) Validate key output in terminal:

- `schema: timelog_extract.truth_payload`
- `version: 1`
- `totals: ...`
- `pdf_path: ...` (when `--pdf` is passed)

6) Validate generated files exist:

```bash
ls output/latest-payload.json
ls output/pdf
```

7) Validate JSON contract via CLI:

```bash
python3 timelog_extract.py --today --format json > /tmp/timelog-today.json
python3 - <<'PY'
import json
data = json.load(open('/tmp/timelog-today.json', 'r', encoding='utf-8'))
print(data.get('schema'), data.get('version'))
PY
```

Expected:

- `timelog_extract.truth_payload 1`

8) Validate empty-range PDF path:

```bash
python3 timelog_extract.py --from 1999-01-01 --to 1999-01-02 --invoice-pdf
```

Expected:

- No crash
- Prints `PDF created: ...timelog-invoice-1999-01-02.pdf`

## Tester Report Template

Use this exact template in PR comment or issue:

```md
## RC CLI-first test report
- Environment: <OS + Python version>
- Fresh clone: PASS/FAIL
- Install (`pip -e .`): PASS/FAIL
- Unit tests: PASS/FAIL
- Engine runner smoke: PASS/FAIL
- JSON schema/version check: PASS/FAIL
- Empty-range PDF check: PASS/FAIL
- Issues observed: <none or list>
- Overall recommendation: GO / NO-GO
```

## Gate Mapping

This script is intended to satisfy:

- Fresh-clone validation
- Human second-tester smoke evidence
- CLI-first go/no-go confidence
