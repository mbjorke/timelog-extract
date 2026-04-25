# Beta onboarding: project config path

Status: draft runbook
Audience: maintainer + early testers

## Purpose

Use this runbook to test whether a new user can get from "Gittan runs" to a
useful `timelog_projects.json` without hand-editing every rule.

This is not an invoice-approval workflow. It is the first controlled path toward
useful classified time: observed evidence, suggested mappings, explicit approval
before config writes.

## Success Bar

A beta onboarding session is successful when the tester can:

1. install or run Gittan,
2. see source/setup status,
3. generate a read-only triage plan,
4. recognize at least one real work window from domains + timestamp hints,
5. approve or reject suggested project mappings,
6. rerun a report and see uncategorized time move in the expected direction.

## Invite Wording

Use this framing when recruiting early testers:

> Gittan is not an automatic invoice-truth machine yet. I am looking for a few
> people with messy AI/dev workflows who want to test whether a local,
> evidence-first setup can get from raw activity to a useful project config
> quickly. The beta goal is to measure onboarding friction and trust, not to
> outsource billing judgment.

Good fit:

- solo consultants, founders, or AI-heavy developers who already struggle to
reconstruct project time,
- people willing to run a local CLI and give feedback on confusing steps,
- people who understand that classified time is a candidate record until they
approve it.

Not a fit yet:

- users who need hands-off invoice automation on day one,
- teams requiring centralized cloud dashboards or admin controls,
- users who cannot safely inspect local activity traces on their own machine.

## Private Beta Readiness Gate

Do not invite a tester into the config-onboarding beta until these are true:

- `gittan -V` works from a normal shell.
- `gittan doctor` gives understandable next steps.
- `gittan report --today --source-summary` completes or fails with an
actionable source warning.
- `gittan triage --json` produces a read-only plan or a clear empty reason.
- The tester understands that no raw private data should be posted publicly.

## Tester Script

Use a copied or disposable project config when possible. Do not ask testers to
share raw private data.

1. Check the install and environment:
  - `gittan -V`
  - `gittan doctor`
2. Run a normal report:
  - `gittan report --today --source-summary`
3. Generate a read-only onboarding plan:
  - `gittan triage --json`
4. Review:
  - top domains,
  - `first_seen_local` / `last_seen_local`,
  - `sample_window_local`,
  - suggested project choices.
5. If a mapping is clearly right, apply with a dry run first:
  - `gittan triage-apply --dry-run --input decisions.json`
6. Apply only after the tester explicitly approves:
  - `gittan triage-apply --input decisions.json`

## Decisions File Example

Create `decisions.json` only from mappings the tester recognizes and approves.
Use exact project names from `timelog_projects.json`.

```json
{
  "decisions": [
    {
      "project_name": "Example Client",
      "rule_type": "tracked_urls",
      "rule_value": "example.com"
    }
  ]
}
```

Prefer `tracked_urls` for stable domains. Use `match_terms` only for project
specific phrases, issue keys, product names, or repo names that are unlikely to
match another customer.

## Feedback To Capture

- Time from first command to first useful mapping.
- Which step felt confusing or too manual.
- Whether timestamp hints helped recognize the project.
- Whether suggestions felt too conservative, too broad, or about right.
- Whether the tester trusted the proposed config write.
- Any source that was missing but expected.

## Feedback Template

```text
Install/setup result:
First useful mapping time:
Mapping recognized from timestamp hints? yes/no
Suggestion quality: too narrow / about right / too broad
Dry-run apply clear? yes/no
Biggest confusion:
Missing source or signal:
Would you run this again tomorrow? yes/no
Private data shared publicly? no
```

## Truth Standard Alignment

This path follows `docs/specs/timelog-truth-standard-rfc.md`:

- domains and timestamp hints are observed evidence,
- suggested mappings are classified candidates,
- config writes require explicit human approval,
- approved invoice time remains a later, separate decision.

## Non-Goals

- Do not promise automatic invoice truth.
- Do not require cloud inference.
- Do not ask testers to paste raw browser history, private project config, or
customer-sensitive domains into public channels.
- Do not optimize for broad beta volume before this path is clear for a handful
of design partners.

## Next Product Decision

If this runbook still feels too manual after 2-3 real sessions, the next product
increment should be a guided `gittan setup` / `gittan triage` path that turns the
same evidence plan into a small interactive project-config wizard.