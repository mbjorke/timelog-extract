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
**Prevention:** Always register a custom redirect handler on openers managing authentication tokens to explicitly reject plain HTTP redirects, protecting headers from cross-protocol leaks.

## 2026-08-02 - Standalone Script HTTP Hardening
**Vulnerability:** Standalone testing scripts (such as `briox_connection_test.py`) that perform external API calls and transmit sensitive authorization headers (such as `Authorization` tokens) can be vulnerable to credential leakage if they do not validate URL schemes or block insecure HTTP redirects.
**Learning:** Security gates should not be limited only to the main application boundaries. Any script/utility included in the codebase that handles sensitive user/API credentials must use a secure opener (e.g. custom `RejectHttpRedirectHandler`) and validate that targets are strictly HTTPS.
**Prevention:** Ensure all standalone utility scripts enforce scheme validation on target endpoints and explicitly construct custom `urllib` openers that reject plain HTTP redirects.
