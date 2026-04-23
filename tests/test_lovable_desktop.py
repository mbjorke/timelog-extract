"""Tests for Lovable Desktop (Electron) history discovery."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from collectors.lovable_desktop import (
    _filter_lovable_storage_urls,
    _extract_lovable_urls,
    collect_lovable_desktop,
    lovable_desktop_history_candidates,
    lovable_desktop_root,
)


class LovableDesktopTests(unittest.TestCase):
    def test_root_path(self):
        home = Path("/Users/example")
        self.assertEqual(
            lovable_desktop_root(home),
            home / "Library" / "Application Support" / "lovable-desktop",
        )

    def test_candidates_empty_when_missing(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(lovable_desktop_history_candidates(home), [])

    def test_candidates_finds_nonempty_history_files(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hist = home / "Library/Application Support/lovable-desktop/Default/History"
            hist.parent.mkdir(parents=True)
            hist.write_bytes(b"\x00" * 4096)
            paths = lovable_desktop_history_candidates(home)
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0].resolve(), hist.resolve())

    def test_candidates_skips_zero_byte_files(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hist = home / "Library/Application Support/lovable-desktop/Default/History"
            hist.parent.mkdir(parents=True)
            hist.write_bytes(b"")
            self.assertEqual(lovable_desktop_history_candidates(home), [])

    def test_extract_lovable_urls_from_blob(self):
        blob = (
            b"prefix https://lovable.dev/foo bar "
            b"https://id-preview--abc.lovable.app/path?q=1 "
            b"https://x.lovableproject.com/hello "
            b"https://id-preview--uuid.lov "
            b"https://uuid.lovableproject. suffix"
        )
        urls = _extract_lovable_urls(blob)
        self.assertIn("https://lovable.dev/foo", urls)
        self.assertTrue(any("lovable.app/path" in u for u in urls))
        self.assertTrue(any("lovableproject.com/hello" in u for u in urls))
        self.assertIn("https://id-preview--uuid.lov", urls)
        self.assertIn("https://uuid.lovableproject.", urls)

    def test_filter_lovable_storage_urls_strict_drops_invalid_host_variants(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://id-preview--abc.lovable.app/path",
            "https://x.lovableproject.com/hello",
            "https://lovable.devyO",
            "https://lovable.dev116cS",
            "https://lovable.dev4:e",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="strict")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertIn("https://id-preview--abc.lovable.app/path", filtered)
        self.assertIn("https://x.lovableproject.com/hello", filtered)
        self.assertNotIn("https://lovable.devyO", filtered)
        self.assertNotIn("https://lovable.dev116cS", filtered)
        self.assertNotIn("https://lovable.dev4:e", filtered)

    def test_filter_lovable_storage_urls_balanced_salvages_noisy_lovable_dev_variants(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://id-preview--abc.lovable.app/path",
            "https://4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovableproject.",
            "https://id-preview--4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lov",
            "https://lovable.devyO",
            "https://lovable.dev116cS",
            "https://lovable.dev4:e",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertIn("https://id-preview--abc.lovable.app/path", filtered)
        self.assertIn("https://4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovableproject.com", filtered)
        self.assertIn("https://id-preview--4a0b0b28-b23f-418c-aa1c-dfabc21b21ad.lovable.app", filtered)
        self.assertIn("https://lovable.dev", filtered)

    def test_filter_lovable_storage_urls_balanced_skips_malformed_urls_without_crashing(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://[broken-url",
        ]
        filtered = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertIn("https://lovable.dev/projects/abc", filtered)
        self.assertNotIn("https://[broken-url", filtered)

    def test_collect_lovable_desktop_falls_back_to_storage_when_history_has_no_rows(self):
        dt = datetime.now(timezone.utc)
        sentinel = [{"source": "Lovable (desktop)", "detail": "storage signal — x", "project": "Time Log Genius"}]
        with patch("collectors.lovable_desktop.lovable_desktop_history_candidates", return_value=[Path("/tmp/History")]):
            with patch("collectors.lovable_desktop.query_chrome", return_value=[]):
                with patch("collectors.lovable_desktop._collect_lovable_desktop_from_storage", return_value=sentinel) as fb:
                    out = collect_lovable_desktop(
                        profiles=[],
                        dt_from=dt,
                        dt_to=dt,
                        collapse_minutes=15,
                        home=Path("/tmp"),
                        epoch_delta_us=0,
                        classify_project=lambda text, profiles: "Unknown",
                        make_event=lambda source, ts, detail, project: {
                            "source": source,
                            "local_ts": ts,
                            "detail": detail,
                            "project": project,
                        },
                        lovable_noise_profile="balanced",
                    )
        self.assertEqual(out, sentinel)
        fb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
