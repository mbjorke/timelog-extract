"""Chrome History timestamp epoch offset (shared by report pipeline and triage helpers)."""

# Microseconds between Chrome's webkit epoch (1601-01-01) and Unix epoch (1970-01-01).
CHROME_EPOCH_DELTA_US = 11_644_473_600 * 1_000_000
