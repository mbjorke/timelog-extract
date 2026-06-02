# Mapping calendar title codes to projects

Status: how-to  
Last updated: 2026-06-01

## Who this is for

People who already encode the project in the calendar **event title** as a
prefix or code — for example `HÅ-DAA standup`, `EASE-DAA review`, or
`KidneySign proteomics data` (see the
[Pierre persona](../product/persona-pierre-calendar-timereport.md)). Gittan can
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
  configured as `HÅ-DAA` matches `hå-daa` in a title and vice versa;
- **substring, anywhere in the title** — the code does not have to be a prefix;
  `Quick sync about HÅ-DAA` still classifies;
- **multi-code per project** — list several codes under one project when you use
  more than one (e.g. `HÅ-DAA` and `EASE-DAA` both → one project).

Unrecognized titles are **not** force-fit to a project; they fall back to
`Uncategorized` rather than guessing.

## Example

```json
{
  "projects": [
    {
      "name": "DAA",
      "match_terms": ["HÅ-DAA", "EASE-DAA"]
    },
    {
      "name": "EuCo",
      "match_terms": ["HÅ-EuCo"]
    },
    {
      "name": "KidneySign",
      "match_terms": ["KidneySign"]
    }
  ]
}
```

With this config:

| Calendar title | Classified project |
| --- | --- |
| `HÅ-DAA standup` | DAA |
| `EASE-DAA review` | DAA |
| `HÅ-EuCo planning` | EuCo |
| `KidneySign proteomics data` | KidneySign |
| `Dentist appointment` | Uncategorized |

Then review by week with `gittan report --weekly` (ISO week × project pivot).

## Tips

- Keep codes **specific**. A generic term (e.g. `sync`) will match unrelated
  titles; prefer the distinctive code you already use.
- If two projects share a code, classification picks the strongest match — give
  each project its own distinct code to avoid ambiguity.
- Future: Gittan can scan your calendar history and **propose** these mappings
  automatically (backlog item P7 in
  [`../product/calendar-beat-the-parser-backlog.md`](../product/calendar-beat-the-parser-backlog.md)).

## Behavior Contract

```gherkin
Feature: Calendar title-code classification
  Calendar event titles that encode a project code map to that project.

  Scenario: A title code classifies to its project
    Given a project profile lists "HÅ-DAA" in its match_terms
    And the Calendar source is enabled
    When an event titled "HÅ-DAA standup" is collected
    Then the event should be classified to that project

  Scenario: Matching ignores letter case
    Given a project profile lists "HÅ-DAA" in its match_terms
    When an event titled "hå-daa lowercase title" is collected
    Then the event should still classify to that project

  Scenario: An unrecognized title is not force-fit
    Given no project profile matches the title
    When an event titled "Dentist appointment" is collected
    Then it should fall back to Uncategorized
```

Coverage: `tests/test_calendar_code_classification.py`.
