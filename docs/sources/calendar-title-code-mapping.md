# Mapping calendar title codes to projects

Status: how-to  
Last updated: 2026-06-01

## Who this is for

People who already encode the project in the calendar **event title** as a
prefix or code — for example `TÖ-ABC standup`, `WIDE-ABC review`, or
`DataForge proteomics data` (see the
[Robin persona](../product/persona-robin-calendar-timereport.md)). Gittan can
turn those titles into project hours automatically, with no change to how you
keep your calendar.

## How it works

When the Calendar source is enabled (`--calendar-source on`, see
[`sources-and-flags.md`](sources-and-flags.md)), each event's **title is run
through the same project classifier as every other source**. You map a code to a
project by adding the code to that project's `match_terms` in your projects
config.

Matching is:

- **case-insensitive** — `match_terms` and titles are both lowercased, so a code
  configured as `TÖ-ABC` matches `tö-abc` in a title and vice versa;
- **substring, anywhere in the title** — the code does not have to be a prefix;
  `Quick sync about TÖ-ABC` still classifies;
- **multi-code per project** — list several codes under one project when you use
  more than one (e.g. `TÖ-ABC` and `WIDE-ABC` both → one project).

Unrecognized titles are **not** force-fit to a project; they fall back to
`Uncategorized` rather than guessing.

## Example

```json
{
  "projects": [
    {
      "name": "ABC",
      "match_terms": ["TÖ-ABC", "WIDE-ABC"]
    },
    {
      "name": "MiCo",
      "match_terms": ["TÖ-MiCo"]
    },
    {
      "name": "DataForge",
      "match_terms": ["DataForge"]
    }
  ]
}
```

With this config:

| Calendar title | Classified project |
| --- | --- |
| `TÖ-ABC standup` | ABC |
| `WIDE-ABC review` | ABC |
| `TÖ-MiCo planning` | MiCo |
| `DataForge proteomics data` | DataForge |
| `Dentist appointment` | Uncategorized |

Then review by week with `gittan report --weekly` (ISO week × project pivot).

## Tips

- Keep codes **specific**. A generic term (e.g. `sync`) will match unrelated
  titles; prefer the distinctive code you already use.
- If two projects share a code, classification picks the strongest match — give
  each project its own distinct code to avoid ambiguity.
## Get the codes proposed for you

Instead of writing the codes by hand, let Gittan scan your calendar history and
**propose** the project stubs:

```bash
gittan calendar-suggest --calendar-names "TimeReport"
```

It reads the named calendar(s) read-only, finds distinctive codes
(hyphenated like `TÖ-ABC`, CamelCase like `DataForge`, ALL-CAPS like `ACME`,
dotted like `examplelab.test`), skips codes already in your config, ranks them by
how often they appear, and prints ready-to-paste profile stubs. It **never writes
config** — review and paste the ones you want. Use `--format json` for scripting,
`--days N` to widen the lookback, and `--min-count N` to filter rare codes.

A bare single-word project name (e.g. `Strike`) is indistinguishable from an
ordinary word, so it is not proposed — add those by hand.

## Behavior Contract

```gherkin
Feature: Calendar title-code classification
  Calendar event titles that encode a project code map to that project.

  Scenario: A title code classifies to its project
    Given a project profile lists "TÖ-ABC" in its match_terms
    And the Calendar source is enabled
    When an event titled "TÖ-ABC standup" is collected
    Then the event should be classified to that project

  Scenario: Matching ignores letter case
    Given a project profile lists "TÖ-ABC" in its match_terms
    When an event titled "tö-abc lowercase title" is collected
    Then the event should still classify to that project

  Scenario: An unrecognized title is not force-fit
    Given no project profile matches the title
    When an event titled "Dentist appointment" is collected
    Then it should fall back to Uncategorized
```

Coverage: `tests/test_calendar_code_classification.py`.
