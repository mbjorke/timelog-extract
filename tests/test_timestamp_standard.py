"""The timestamp standard's parsing claims, pinned as tests.

`docs/specs/timestamp-standard.md` §4 makes two kinds of claim. One is about speed,
and belongs in `scripts/bench_timestamp_parsing.py` — timings cannot be asserted in
CI without producing a flaky gate on a shared runner.

The other kind is about *correctness on the supported floor*, and that is what
these tests hold. The standard tells a future author "strip `Z` first", "use int
slicing for compact formats", "slice long stamps to 26 characters". Each of those
exists because the naive alternative raises `ValueError` on Python 3.10 while
passing on 3.11+ — a defect no local run on a modern interpreter would reveal. So
the rules are asserted here rather than trusted to be read.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class FloorSafeParsingTests(unittest.TestCase):
    """What `fromisoformat` accepts on 3.10 is narrower than on 3.11+.

    These assert the *documented idiom* works, not that the bare call does — on
    3.11+ the bare call would pass too, which is exactly the trap.
    """

    def test_isoformat_shaped_input_parses_directly(self):
        for text in (
            "2026-07-26",
            "2026-07-26 10:10",
            "2026-07-26T10:10:00",
            "2026-07-26T10:10:00.123456+00:00",
        ):
            with self.subTest(text=text):
                self.assertIsInstance(datetime.fromisoformat(text), datetime)

    def test_z_suffix_is_normalized_before_parsing(self):
        """GitHub and Claude transcripts both emit `Z`; 3.10 rejects it."""
        text = "2026-07-26T10:10:00Z"
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_compact_format_uses_int_slicing_not_fromisoformat(self):
        """`20260709T162324` cannot go through fromisoformat on 3.10 at all."""
        name = "20260709T162324"
        self.assertEqual(
            date(int(name[:4]), int(name[4:6]), int(name[6:8])), date(2026, 7, 9)
        )

    def test_over_microsecond_precision_is_sliced_to_26_chars(self):
        """Log lines carry more precision than fromisoformat accepts."""
        text = "2026-07-26 10:10:00.123456789"
        parsed = datetime.fromisoformat(text[:26])
        self.assertEqual(parsed.microsecond, 123456)

    def test_naive_input_is_given_utc_explicitly(self):
        """§1: a naive datetime reaching storage is a bug."""
        parsed = datetime.fromisoformat("2026-07-26 10:10")
        self.assertIsNone(parsed.tzinfo)
        parsed = parsed.replace(tzinfo=timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-07-26T10:10:00+00:00")


class DocumentedIdiomsMatchStrptimeTests(unittest.TestCase):
    """Each faster idiom must return the value `strptime` would.

    A performance win that changes the parsed value is not a win, and an hours
    report is exactly the place a silently-shifted timestamp would go unnoticed.
    """

    def test_date_only(self):
        self.assertEqual(
            datetime.fromisoformat("2026-07-26"),
            datetime.strptime("2026-07-26", "%Y-%m-%d"),
        )

    def test_worklog_stamp(self):
        self.assertEqual(
            datetime.fromisoformat("2026-07-26 10:10"),
            datetime.strptime("2026-07-26 10:10", "%Y-%m-%d %H:%M"),
        )

    def test_log_line_with_microseconds(self):
        text = "2026-07-26 10:10:00.123456"
        self.assertEqual(
            datetime.fromisoformat(text[:26]),
            datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f"),
        )

    def test_compact_folder_name(self):
        name = "20260709T162324"
        self.assertEqual(
            date(int(name[:4]), int(name[4:6]), int(name[6:8])),
            datetime.strptime(name[:8], "%Y%m%d").date(),
        )


class BenchmarkScriptTests(unittest.TestCase):
    """The script backing §4 must stay runnable, or the standard loses its evidence."""

    def test_benchmark_runs_and_verifies_equivalence(self):
        script = REPO_ROOT / "scripts" / "bench_timestamp_parsing.py"
        self.assertTrue(script.exists(), f"{script} is cited by the standard")
        # A tiny iteration count: this asserts the equivalence gate and the exit
        # code, not the timings.
        result = subprocess.run(
            [sys.executable, str(script), "--iterations", "50"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode, 0, f"benchmark reported a mismatch:\n{result.stdout}\n{result.stderr}"
        )
        self.assertIn("identical to strptime", result.stdout)


class StandardDocTests(unittest.TestCase):
    """The doc must cite the script rather than only a number."""

    def test_standard_points_at_the_benchmark(self):
        text = (REPO_ROOT / "docs" / "specs" / "timestamp-standard.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/bench_timestamp_parsing.py", text)


if __name__ == "__main__":
    unittest.main()
