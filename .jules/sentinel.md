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

## 2026-08-05 - Defense-in-Depth Opener-Level Plain HTTP Interception
**Vulnerability:** Initial connections to configured API endpoints could inadvertently transmit credentials over plain HTTP if the user misconfigured or manipulated the endpoint scheme, even if redirect blocking is active.
**Learning:** Reusable HTTP redirect handlers (`RejectHttpRedirectHandler` and Jira's `_RejectHttpRedirectHandler`) can implement standard urllib's `http_request` hook to intercept and block all initial requests using the insecure `http://` protocol at the Opener level before any packet is sent, providing complete defense-in-depth across the application's API collectors.
**Prevention:** Integrate both request-level and redirect-level protocol validation into a shared security handler to guarantee credentials never hit unencrypted channels under any scenario.
