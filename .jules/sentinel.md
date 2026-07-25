# Sentinel 🛡️ Security Journal

This journal tracks critical security learnings, vulnerability patterns specific to this codebase, unexpected side-effects, or important constraints.

*Do not log routine work or generic security best practices.*

## 2026-07-23 - Strict HTTPS Enforcement for External Integrations
**Vulnerability:** Transmitting sensitive Basic Authentication credentials (email + API token) over unencrypted HTTP when an insecure base URL is configured.
**Learning:** Checking URL scheme was only implemented in the onboarding credential-verification flow (`verify_jira_credentials`), leaving the actual integration methods (`list_jira_worklogs` and `post_jira_worklog`) open to transmitting sensitive data over unencrypted channels if an insecure URL bypasses verification.
**Prevention:** Enforce security constraints (e.g., protocol validations) directly at the boundaries of the action functions/clients themselves, ensuring defense in depth rather than relying on interactive onboarding-only gates.
