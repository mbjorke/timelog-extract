# Sentinel 🛡️ Security Journal

This journal tracks critical security learnings, vulnerability patterns specific to this codebase, unexpected side-effects, or important constraints.

*Do not log routine work or generic security best practices.*

## 2026-07-23 - Strict HTTPS Enforcement for External Integrations
**Vulnerability:** Transmitting sensitive Basic Authentication credentials (email + API token) over unencrypted HTTP when an insecure base URL is configured.
**Learning:** Checking URL scheme was only implemented in the onboarding credential-verification flow (`verify_jira_credentials`), leaving the actual integration methods (`list_jira_worklogs` and `post_jira_worklog`) open to transmitting sensitive data over unencrypted channels if an insecure URL bypasses verification.
**Prevention:** Enforce security constraints (e.g., protocol validations) directly at the boundaries of the action functions/clients themselves, ensuring defense in depth rather than relying on interactive onboarding-only gates.

## 2026-07-25 - Extensible Redirect Blocking for REST Collectors
**Vulnerability:** Standard library `urllib.request.urlopen` following insecure HTTP redirects and forwarding sensitive Authorization bearer tokens/headers to unencrypted HTTP channels.
**Learning:** External integrations like GitHub and Toggl require similar protection levels as Jira. Reusing localized, customized `urlopen` functions with `_RejectHttpRedirectHandler` redirect blocking and initial scheme validations ensures credentials are never transmitted over plain text channels, even across custom redirect sequences.
**Prevention:** Always register a water-tight custom redirect handler on openers managing authentication tokens to explicitly reject plain HTTP redirects, protecting headers from cross-protocol leaks.

## 2026-08-03 - Enforcing Security Hardening in Standalone Utilities
**Vulnerability:** Standalone testing/connection utilities (like `briox_connection_test.py`) using raw standard library `urllib.request.urlopen` without scheme verification or custom redirect filters, exposing sensitive credentials to cleartext transport or insecure downgrade redirections.
**Learning:** Non-production/standalone script targets are often overlooked in security updates but may handle production-level environment secrets. Applying the identical strict `RejectHttpRedirectHandler` pattern and explicit HTTPS validation checks directly within standalone helpers ensures defense-in-depth security covers developer scripts.
**Prevention:** Secure standalone HTTP clients with the same rigorous redirect filtering and HTTPS schema gating rules as those built into production collector pipelines.
