"""The file-length gate warns in a soft band before the hard cap.

The 500-line rule was silently accepting files trimmed to just under the limit;
the warning band surfaces "approaching the cap" so decomposition happens before
CI turns red.
"""

from __future__ import annotations

import unittest

from scripts.check_file_lengths import classify_lengths


class ClassifyLengthsTests(unittest.TestCase):
    def test_over_cap_is_a_violation(self):
        violations, warnings = classify_lengths([("a.py", 501)], max_lines=500, warn_lines=460)
        self.assertEqual(violations, [("a.py", 501)])
        self.assertEqual(warnings, [])

    def test_within_band_is_a_warning_not_a_violation(self):
        violations, warnings = classify_lengths([("a.py", 499)], max_lines=500, warn_lines=460)
        self.assertEqual(violations, [])
        self.assertEqual(warnings, [("a.py", 499)])

    def test_at_cap_exactly_warns_but_does_not_fail(self):
        violations, warnings = classify_lengths([("a.py", 500)], max_lines=500, warn_lines=460)
        self.assertEqual(violations, [])
        self.assertEqual(warnings, [("a.py", 500)])

    def test_below_band_is_silent(self):
        violations, warnings = classify_lengths([("a.py", 459)], max_lines=500, warn_lines=460)
        self.assertEqual(violations, [])
        self.assertEqual(warnings, [])

    def test_mixed_set_is_partitioned(self):
        counts = [("ok.py", 100), ("near.py", 480), ("edge.py", 500), ("over.py", 520)]
        violations, warnings = classify_lengths(counts, max_lines=500, warn_lines=460)
        self.assertEqual(violations, [("over.py", 520)])
        self.assertEqual(sorted(warnings), [("edge.py", 500), ("near.py", 480)])


if __name__ == "__main__":
    unittest.main()
