# Decision: Private-first, not local-first

Status: **active** (mechanism shipped 2026-07-25; vision docs still to be updated)  
Owner: Maintainer  
Last updated: 2026-07-25

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

## The store: one data repo, one file per device

The supported home for the data layer is the user's own `~/.gittan` git repo —
already committed by `scripts/gittan_data_autocommit.sh` (`git add -A` in
`$GITTAN_HOME`, push opt-in to a **private** remote). The evidence ledger lives
at `~/.gittan/evidence/`, inside that tree, so it is already carried.

Sharing one repo across devices raised one real problem, measured rather than
assumed: the ledger's `prev_hash` chain is order-dependent per file, so when two
devices appended to the same monthly file and git resolved the conflict by
keeping both sides, both chains verified fine individually and the merged file
did not (`prev_hash does not match previous record`). Every record was genuine;
only the ordering was.

The fix is to remove the collision rather than resolve it:

- Evidence is filed as **`YYYY-MM.<device-slug>-<8hex>.jsonl`**, from the device recorded in
  each record's `source_provenance`. Device labels must be **unique per machine**
  (host name by default; `--device` overrides). A collision recreates the merge
  problem. Distinct labels → each device only ever writes its own file, so git
  has nothing to merge and every file keeps a valid chain.
- Reading already unions all `*.jsonl` and dedupes by fingerprint, so the same
  observation captured on two devices still counts once.
- Records without a device keep the plain `YYYY-MM.jsonl` name; existing stores
  are read unchanged and are never rewritten.
- `gittan evidence --repair` re-links chains and drops duplicates for a store
  that was already merged the old way.

What this deliberately is not: a sync service. The repo is the user's, the remote
is the user's, and Gittan never operates either.

## Related

- `docs/specs/intent-capture.md` — first feature shaped by this decision.
- `docs/specs/local-evidence-shadow-log.md` — retention layer; same storage
  philosophy.
- `docs/task-prompts/device-session-capture-task.md` — capturing evidence from a
  device that is not the main machine.
- `docs/runbooks/gittan-data-autocommit.md` / `#237` — automating the commit side.
