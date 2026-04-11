# v1.0.0 Tag Annotation Draft

CLI-first stable release for Timelog Extract.

- Local-only aggregation of development activity signals into project/customer reporting.
- Stable truth payload contract for automation (`timelog_extract.truth_payload`, `version: "1"`).
- Reliable script-first run path:
  - `python3 scripts/run_engine_report.py --today --pdf --json-file output/latest-payload.json`
- Optional extension remains beta companion; CLI is the primary v1 path.
