# Privacy and Security Baseline

## Consent UX Requirements

- First-run consent gate before any scan.
- Per-source toggle with plain-language explanation.
- Clear local-only statement: no outbound data transmission in core flow.

## Sensitive Inputs

- Browser history
- Mail metadata
- Local AI session logs
- Screen Time database

Each source must be off by default unless user explicitly enables it.

## Credential Handling

- Do not store API credentials in plaintext project files.
- For plugin flow, store secrets in editor secret storage API.
- CLI fallback may use environment variables for local development only.

## Logging and Diagnostics

- Avoid logging raw message/content payloads by default.
- If diagnostics are enabled, redact:
  - email addresses
  - API tokens
  - full URLs with query parameters

## Packaging Hygiene

- Keep generated artifacts and local data out of git (`output/`, temp files, local configs).
- Keep `TIMELOG.md` excluded from version control.
