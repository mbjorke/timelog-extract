# Source Collector Contract

Status: draft contract  
Last updated: 2026-05-29

## Purpose

Define the minimum behavior every source collector should provide. This keeps
new sources, such as Calendar, from copying one-off patterns from older
collectors.

## Collector Responsibilities

Each source should define:

- source name used in event payloads and source summaries,
- enablement mode (`auto`, `on`, `off`) where applicable,
- consent / permission / configuration checks,
- date-window behavior,
- event identity and deduplication fields,
- shadow-log eligibility and retention fields,
- classification input fields,
- privacy and redaction behavior,
- `collector_status` outcome,
- doctor row behavior when relevant.

## Enablement Modes

| Mode | Expected behavior |
| --- | --- |
| `off` | Do not read backing stores. Return disabled status with a clear reason. |
| `auto` | Run only when prerequisites are present and consent rules allow it. |
| `on` | Try to run; if prerequisites are missing, report disabled/error reason clearly. |

Collectors that do not expose a mode should still behave like `auto` internally:
fail closed, report why, and avoid surprise data reads.

## Date Window Contract

Collectors must:

- read only the requested report window when the backing API supports it,
- filter to the requested window before returning events,
- normalize timestamps consistently with the runtime timezone policy,
- avoid hidden "today" or "now" dependencies in closed-window tests,
- expand recurring or derived events only inside the requested window.

## Event Contract

Returned events should support the existing internal shape:

- `source`
- `timestamp`
- `detail`
- `project`

When available, source-specific metadata should use namespaced/private fields
until the truth payload contract is ready to expose them:

- stable provider event id,
- calendar name / repository / workspace,
- event start and end,
- all-day flag,
- redaction/private flag,
- provenance details needed for debugging.

For sources whose upstream logs are volatile, collectors should provide enough
stable metadata for `docs/specs/local-evidence-shadow-log.md` to retain a useful
local evidence record without copying an entire raw database.

## Collector Status Contract

Every source should make these states distinguishable in `collector_status`:

- disabled by user setting,
- disabled because prerequisites are missing,
- enabled and returned zero events,
- enabled and returned events,
- failed with a collector error.

This is more important than optimistic output. An empty report should be
diagnosable without guessing.

## Doctor Row Contract

Sources with external prerequisites should have doctor coverage:

- configuration present / missing,
- permission present / missing,
- source mode (`auto`, `on`, `off`) when relevant,
- privacy-sensitive notes without printing secrets,
- next action in maintained docs, not `docs/legacy/`.

## Source Weighting

Collectors produce evidence; they do not decide final truth by themselves.
Source roles and weighting are defined in `docs/specs/source-evidence-policy.md`.

New collectors should state which role they serve before implementation.

## Calendar-Specific Notes

Calendar should be implemented as a source only after its behavior contract is
clear:

- Apple Calendar / EventKit is the preferred local-first MVP path on macOS.
- Google Calendar API is a separate opt-in source for users who do not rely on
  Apple Calendar sync.
- Calendar events are scheduled context by default.
- All-day and private events need explicit behavior before code lands.

## Acceptance Checklist

- Source appears in source summary ordering when relevant.
- Source has collector status for enabled, disabled, zero-event, and error cases.
- Source has tests that do not read live user data.
- Source docs state privacy and permission behavior.
- Source states whether and how it can participate in local shadow logging.
- Source behavior maps to at least one Gherkin scenario.
- CLI-facing changes run the CLI impact smoke loop.
