# Timelog Extract (Cursor Extension)

GUI-first extension scaffold for running local timelog extraction.

## Commands

- `Timelog: Open Setup Wizard`
- `Timelog: Open Setup Wizard (Browser Preview)`
- `Timelog: Quick Start`
- `Timelog: Run Report (Today)`
- `Timelog: Run Report (Date Range)`
- `Timelog: Open Output Folder`

The setup wizard now includes:
- explicit local-data consent acknowledgement,
- per-source controls for Chrome, Apple Mail, GitHub, and Screen Time,
- a quick "what will be scanned" summary before running.

## Development

1. `cd cursor-extension`
2. `npm install`
3. `npm run build`
4. Launch extension host from Cursor/VS Code.

The extension calls `core.engine_api` from the workspace root using the configured
Python executable and treats that API as the primary report and PDF contract.
For quick validation without extension-host tooling, use `scripts/run_engine_report.py` from the repo root.