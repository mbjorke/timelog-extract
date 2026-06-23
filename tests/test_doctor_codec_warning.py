"""Doctor must flag a missing cache-evidence codec, not hide it as benign N/A.

A missing zstandard/brotli codec silently zeroes whole evidence sources
(Claude Desktop (Code), Lovable), under-counting AI-heavy days with no obvious
cause. The doctor diagnostic must surface that as a fixable failure.
"""

from __future__ import annotations

import unittest

from core.cache_evidence_health import codec_missing_reason
from core.chromium_cache import CODEC_REINSTALL_HINT


class CodecMissingReasonTests(unittest.TestCase):
    def test_zstandard_missing_is_flagged(self):
        self.assertTrue(
            codec_missing_reason(
                f"zstandard codec missing ({CODEC_REINSTALL_HINT})"
            )
        )

    def test_brotli_degraded_is_flagged(self):
        self.assertTrue(
            codec_missing_reason(
                "Cache present; brotli missing — project titles limited (pip install ...)"
            )
        )

    def test_readable_states_are_not_flagged(self):
        self.assertFalse(codec_missing_reason("Events cache readable"))
        self.assertFalse(codec_missing_reason("Cache readable (35 project titles from cache)"))

    def test_absent_cache_is_not_flagged(self):
        # "No cache yet" is benign — must not read as a codec problem.
        self.assertFalse(
            codec_missing_reason("No Claude Desktop cache yet (open Claude Desktop to create one)")
        )

    def test_empty_reason_is_safe(self):
        self.assertFalse(codec_missing_reason(""))


if __name__ == "__main__":
    unittest.main()
