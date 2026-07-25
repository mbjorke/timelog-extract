"""File length is reported, never enforced.

``classify_lengths`` still separates "over the recommendation" from
"approaching it" — that distinction is useful signal — but neither outcome fails
a build. The exit-code tests below are the ones that pin the policy: advisory by
default, hard only under ``--strict``.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from unittest.mock import patch

from scripts.check_file_lengths import classify_lengths, main


class ClassifyLengthsTests(unittest.TestCase):
    def test_over_the_recommendation_is_reported_separately(self):
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

    def test_exactly_at_warn_line_warns(self):
        # Lower boundary is inclusive (warn_lines <= lines): 460 with warn_lines=460 warns.
        violations, warnings = classify_lengths([("a.py", 460)], max_lines=500, warn_lines=460)
        self.assertEqual(violations, [])
        self.assertEqual(warnings, [("a.py", 460)])

    def test_mixed_set_is_partitioned(self):
        counts = [("ok.py", 100), ("near.py", 480), ("edge.py", 500), ("over.py", 520)]
        violations, warnings = classify_lengths(counts, max_lines=500, warn_lines=460)
        self.assertEqual(violations, [("over.py", 520)])
        self.assertEqual(sorted(warnings), [("edge.py", 500), ("near.py", 480)])


class ExitCodeTests(unittest.TestCase):
    """The policy itself: length never fails a build unless --strict is asked for."""

    def _run(self, argv, lines):
        with patch("sys.argv", ["check_file_lengths.py", *argv]), \
             patch("scripts.check_file_lengths.tracked_python_files", return_value=[Path("x.py")]), \
             patch("scripts.check_file_lengths.count_lines", return_value=lines), \
             patch("pathlib.Path.relative_to", return_value=Path("x.py")):
            return main()

    def test_over_the_recommendation_exits_zero_by_default(self):
        self.assertEqual(self._run(["--max-lines", "500"], 900), 0)

    def test_strict_opts_into_failure(self):
        self.assertEqual(self._run(["--max-lines", "500", "--strict"], 900), 1)

    def test_within_the_recommendation_exits_zero_under_strict(self):
        self.assertEqual(self._run(["--max-lines", "500", "--strict"], 100), 0)


if __name__ == "__main__":
    unittest.main()
