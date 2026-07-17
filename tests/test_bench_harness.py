"""Unit tests for the hot-path benchmark harness (PR #390 follow-up)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.bench_hotpath import (
    _exc_stderr_text,
    _stderr_last_line,
    extract_revision,
)
from scripts.bench_synth_data import generate


class BenchSynthDataTests(unittest.TestCase):
    def test_generate_honors_event_count(self):
        for n in (0, 1, 7, 50, 200):
            with self.subTest(events=n):
                data = generate(n, days=14, n_projects=5, seed=42)
                self.assertEqual(len(data["events"]), n)

    def test_generate_is_reproducible_with_fixed_start_and_tz(self):
        a = generate(
            100,
            days=7,
            n_projects=4,
            seed=99,
            start_date="2024-06-01",
            tz_name="UTC",
        )
        b = generate(
            100,
            days=7,
            n_projects=4,
            seed=99,
            start_date="2024-06-01",
            tz_name="UTC",
        )
        self.assertEqual(a["events"], b["events"])
        self.assertEqual(a["start_date"], "2024-06-01")
        self.assertEqual(a["tz"], "UTC")
        self.assertTrue(a["events"][0]["timestamp"].startswith("2024-06-"))

    def test_generate_uses_neutral_placeholders(self):
        data = generate(80, days=5, n_projects=3, seed=7)
        blob = "\n".join(e["detail"] for e in data["events"])
        self.assertNotIn("DN.se", blob)
        self.assertNotIn("/Users/", blob)
        self.assertNotIn("Lindqvist", blob)
        self.assertNotIn("Nyhetsbrev", blob)
        self.assertNotIn("fakturaunderlag", blob)
        self.assertNotIn("avstämning", blob)

    def test_generate_rejects_invalid_n_projects(self):
        with self.assertRaises(ValueError):
            generate(10, days=2, n_projects=0, seed=1)
        with self.assertRaises(ValueError):
            generate(10, days=2, n_projects=-1, seed=1)
        max_projects = 12 * 10  # FIRST_WORDS * SECOND_WORDS
        with self.assertRaises(ValueError):
            generate(10, days=2, n_projects=max_projects + 1, seed=1)

    def test_generate_normalizes_utc_tz_case(self):
        data = generate(
            5, days=1, n_projects=2, seed=3, start_date="2024-06-01", tz_name="utc"
        )
        self.assertEqual(data["tz"], "UTC")


class BenchHotpathHelpersTests(unittest.TestCase):
    def test_stderr_last_line_whitespace_only(self):
        self.assertEqual(_stderr_last_line("   \n\n  "), "failed")
        self.assertEqual(_stderr_last_line(None), "failed")
        self.assertEqual(_stderr_last_line("oops\n"), "oops")
        self.assertEqual(_stderr_last_line("a\n  \nbad\n  "), "bad")

    def test_exc_stderr_text_tolerates_none(self):
        exc = subprocess.CalledProcessError(1, ["tar"], stderr=None)
        self.assertIn("tar", _exc_stderr_text(exc))
        exc_b = subprocess.CalledProcessError(1, ["tar"], stderr=b"boom\n")
        self.assertEqual(_exc_stderr_text(exc_b), "boom")

    def test_extract_revision_streams_archive_and_captures_tar_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            with mock.patch("scripts.bench_hotpath.subprocess.run") as run:
                run.side_effect = [
                    mock.Mock(returncode=0),
                    subprocess.CalledProcessError(
                        1, ["tar"], stderr=b"tar: failed to extract\n"
                    ),
                ]
                with self.assertRaises(subprocess.CalledProcessError) as ctx:
                    extract_revision("HEAD", dest)
                self.assertEqual(ctx.exception.stderr, b"tar: failed to extract\n")
                git_kwargs = run.call_args_list[0].kwargs
                self.assertIsNotNone(git_kwargs.get("stdout"))
                self.assertEqual(git_kwargs.get("stderr"), subprocess.PIPE)
                self.assertEqual(run.call_args_list[1].kwargs.get("capture_output"), True)
                self.assertIsNotNone(run.call_args_list[1].kwargs.get("stdin"))


if __name__ == "__main__":
    unittest.main()
