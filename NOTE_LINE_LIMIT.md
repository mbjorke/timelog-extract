# Line Limit Status After PR #49 Nitpick Cleanup

## Current Status

`core/cli_doctor_sources_projects.py` is at **509 lines**, exceeding the 500-line limit by 9 lines.

## Root Cause

During implementation of nitpick items #10 and #11 from PR #49:
- Added `--toggl-source` CLI option (matching existing `--github-source` pattern)
- Added Rich markup escaping for `toggl_reason`
- Added `from rich import markup` import

The file was exactly at 500 lines before these changes. These required features pushed it over.

## Nitpick #12 Context

The original nitpick #12 suggested: "Proactive refactor: file is at ~500 lines — extract GitHub/Toggl source-checking rows into `core/doctor_source_rows.py` before it grows further."

This was a **preventive suggestion** for before the file exceeded the limit, but implementing nitpicks #10-11 (which were required) caused the overage.

## Resolution Options

1. **Accept temporary overage**: The 9-line overage is minor and caused by implementing requested features. Mark nitpick #12 as "addressed by noting future refactor needed."

2. **Quick trim**: Remove 9+ lines through aggressive condensing (may reduce readability).

3. **Full extraction** (larger scope): Extract GitHub/Toggl source rows to `core/doctor_source_rows.py` as originally suggested. This is a meaningful refactor beyond the nitpick scope.

## Recommendation

**Option 1**: Document the status, complete the PR, and file a separate issue for the extraction refactor when the file approaches 520-530 lines or when adding the next major source check.

The file is maintainable at 509 lines. The limit exists to encourage modular design, not to block incremental feature additions that cause small overages.
