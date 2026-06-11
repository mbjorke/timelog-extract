# Decision: Private-first, not local-first

Status: draft decision (maintainer direction 2026-06; vision docs not yet updated)  
Owner: Maintainer  
Last updated: 2026-06-10

## Decision

The governing product principle is **private-first**: the user owns and
controls their data, and no third party can read it without explicit user
action. **"Local" is a mechanism, not the promise.**

Earlier documents use "local-first" as shorthand for the privacy promise.
That conflation created artificial constraints: single-machine assumptions,
local-HTTP workarounds for capture surfaces, and an apparent blocker for
multi-device workflows that the actual promise never required.

## What does not change

- The extraction engine runs on-device. Raw traces (IDE logs, browser
  history, mail headers) are read where they live and are never uploaded.
- No Gittan-operated cloud service. No accounts with Gittan. No telemetry.
- Consent and opt-in rules from `docs/security/privacy-security.md` stay
  authoritative.

## What changes

- The **config and intent layer** (`timelog_projects.json`, future intent
  records, triage state) may live in a **user-controlled store**: a synced
  `~/.gittan/` folder (iCloud/Dropbox), a self-hosted backend, or an
  encrypted relay the user operates. Gittan never operates the store.
- Multi-device capture (for example tagging a chat thread from a phone)
  is in-principle allowed, because the constraint is *who can read the
  data*, not *which filesystem it is on*.
- The documented default for v1.x remains zero new infrastructure: a
  user-synced `~/.gittan/` folder is the supported pattern before any sync
  backend is designed.

## Follow-ups (not yet done)

- Update wording in `docs/product/gittan-vision.md`, `docs/product/v1-scope.md`,
  and `docs/ideas/simple-invoicing-model.md` where "no remote service" is
  used as a proxy for privacy. The accurate rule: **no Gittan-operated
  remote service; no third-party access without explicit user action.**
- Root `VISION.md` manifesto refresh per `docs/product/vision-documents.md`
  precedence rules.

## Related

- `docs/specs/intent-capture.md` — first feature shaped by this decision.
- `docs/specs/local-evidence-shadow-log.md` — retention layer; same storage
  philosophy.
