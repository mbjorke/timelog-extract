# Timelog Extract (Cursor Extension)

GUI-first extension scaffold for running local timelog extraction.

## Commands

- `Timelog: Open Setup Wizard`
- `Timelog: Run Report (Today)`
- `Timelog: Run Report (Date Range)`
- `Timelog: Open Output Folder`

## Development

1. `cd cursor-extension`
2. `npm install`
3. `npm run build`
4. Launch extension host from Cursor/VS Code.

The extension runs `timelog_extract.py` from the workspace root using the configured Python executable.
