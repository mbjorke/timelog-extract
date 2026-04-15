"""Tests for Lovable Desktop (Electron) history discovery."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.lovable_desktop import (
    _extract_lovable_urls,
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
            b"https://x.lovableproject.com/hello suffix"
        )
        urls = _extract_lovable_urls(blob)
        self.assertIn("https://lovable.dev/foo", urls)
        self.assertTrue(any("lovable.app/path" in u for u in urls))
        self.assertTrue(any("lovableproject.com/hello" in u for u in urls))


if __name__ == "__main__":
    unittest.main()
