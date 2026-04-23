"""Tests for Lovable Desktop (Electron) history discovery."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.lovable_desktop import (
    _canonicalize_lovable_storage_url,
    _extract_lovable_urls,
    _filter_lovable_storage_urls,
    _is_plausible_lovable_storage_url,
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


class LovableExtractUrlsTests(unittest.TestCase):
    """Tests for the updated _extract_lovable_urls (marker-based filter)."""

    def test_skips_non_lovable_https_urls(self):
        """URLs without a lovable domain marker are excluded."""
        blob = b"https://example.com/foo https://github.com/bar"
        self.assertEqual(_extract_lovable_urls(blob), [])

    def test_extracts_lovable_dev_url(self):
        """lovable.dev URLs are extracted."""
        blob = b"https://lovable.dev/projects/abc123"
        urls = _extract_lovable_urls(blob)
        self.assertIn("https://lovable.dev/projects/abc123", urls)

    def test_extracts_lovable_app_url(self):
        """lovable.app URLs are extracted."""
        blob = b"prefix https://id-preview--abc.lovable.app/path suffix"
        urls = _extract_lovable_urls(blob)
        self.assertTrue(any("lovable.app" in u for u in urls))

    def test_extracts_lovableproject_url(self):
        """lovableproject URLs are extracted."""
        blob = b"https://abc.lovableproject.com/foo"
        urls = _extract_lovable_urls(blob)
        self.assertTrue(any("lovableproject" in u for u in urls))

    def test_extracts_lov_dot_marker(self):
        """URLs containing .lov are extracted (partial truncation case)."""
        blob = b"https://id.lov/something"
        urls = _extract_lovable_urls(blob)
        self.assertTrue(len(urls) >= 1)

    def test_deduplicates_repeated_urls(self):
        """Same URL appearing multiple times is returned only once."""
        blob = b"https://lovable.dev/ https://lovable.dev/ https://lovable.dev/"
        urls = _extract_lovable_urls(blob)
        self.assertEqual(urls.count("https://lovable.dev/"), 1)

    def test_empty_bytes_returns_empty(self):
        """Empty bytes returns empty list."""
        self.assertEqual(_extract_lovable_urls(b""), [])


class LovablePlausibleUrlTests(unittest.TestCase):
    """Tests for _is_plausible_lovable_storage_url."""

    def test_valid_lovable_dev(self):
        """lovable.dev root URL is plausible."""
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovable.dev/"))

    def test_valid_subdomain_lovable_app(self):
        """Subdomain of lovable.app is plausible."""
        self.assertTrue(_is_plausible_lovable_storage_url("https://preview--abc.lovable.app/path"))

    def test_valid_lovableproject_com(self):
        """lovableproject.com is plausible."""
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovableproject.com/project/x"))

    def test_non_lovable_domain_rejected(self):
        """Non-lovable domains are rejected."""
        self.assertFalse(_is_plausible_lovable_storage_url("https://example.com/lovable.dev"))

    def test_empty_host_rejected(self):
        """URL with no host is rejected."""
        self.assertFalse(_is_plausible_lovable_storage_url("https:///path"))

    def test_empty_string_rejected(self):
        """Empty string is rejected."""
        self.assertFalse(_is_plausible_lovable_storage_url(""))

    def test_non_printable_chars_rejected(self):
        """URLs with non-printable characters are rejected."""
        url = "https://lovable.dev/\x01binary"
        self.assertFalse(_is_plausible_lovable_storage_url(url))

    def test_subdomain_of_lovable_dev_is_plausible(self):
        """Subdomain of lovable.dev is plausible."""
        self.assertTrue(_is_plausible_lovable_storage_url("https://api.lovable.dev/"))

    def test_partial_host_garbage_rejected(self):
        """Garbage host that merely contains 'lovable' is not plausible."""
        self.assertFalse(_is_plausible_lovable_storage_url("https://notlovable.evil.com/"))


class LovableCanonicalizeUrlTests(unittest.TestCase):
    """Tests for _canonicalize_lovable_storage_url."""

    def test_valid_url_unchanged(self):
        """Already-valid lovable.dev URL is returned as-is."""
        url = "https://lovable.dev/projects/abc"
        result = _canonicalize_lovable_storage_url(url)
        self.assertEqual(result, url)

    def test_truncated_lov_host_recovered(self):
        """Host ending in .lov is recovered to .lovable.app."""
        url = "https://something.lov/path"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_host_lov_alone_becomes_lovable_app(self):
        """Host 'lov' alone becomes lovable.app."""
        result = _canonicalize_lovable_storage_url("https://lov/path")
        self.assertIn("lovable.app", result)

    def test_lovableproject_without_com_recovered(self):
        """Host 'lovableproject' (without .com) is recovered."""
        result = _canonicalize_lovable_storage_url("https://lovableproject/path")
        self.assertIn("lovableproject.com", result)

    def test_lovable_dev_garbage_appended_returns_root(self):
        """Garbage appended to lovable.dev host returns canonical root."""
        result = _canonicalize_lovable_storage_url("https://lovable.devXXXgarbage/path")
        self.assertEqual(result, "https://lovable.dev")

    def test_non_printable_stripped(self):
        """Non-printable characters are stripped before parsing."""
        url = "https://lovable.dev\x00/path"
        result = _canonicalize_lovable_storage_url(url)
        # Should not crash and should return something reasonable
        self.assertIsInstance(result, str)

    def test_empty_string_returns_empty_or_string(self):
        """Empty input returns empty string."""
        result = _canonicalize_lovable_storage_url("")
        self.assertEqual(result, "")

    def test_path_contains_lovable_app_salvages_url(self):
        """When host is broken but path contains lovable.app, URL is salvaged."""
        result = _canonicalize_lovable_storage_url("https://brokenhostXX/lovable.app/project")
        self.assertIn("lovable.app", result)


class LovableFilterStorageUrlsTests(unittest.TestCase):
    """Tests for _filter_lovable_storage_urls."""

    def _sample_urls(self):
        return [
            "https://lovable.dev/projects/abc",
            "https://lovable.dev\x01garbage",  # non-printable
            "https://example.com/other",  # not lovable
        ]

    def test_normal_profile_returns_all(self):
        """normal profile returns all URLs without filtering."""
        urls = self._sample_urls()
        result = _filter_lovable_storage_urls(urls, "normal")
        self.assertEqual(result, urls)

    def test_strict_profile_filters_non_plausible(self):
        """strict profile removes non-plausible URLs (non-lovable, non-printable)."""
        urls = self._sample_urls()
        result = _filter_lovable_storage_urls(urls, "strict")
        self.assertIn("https://lovable.dev/projects/abc", result)
        self.assertNotIn("https://example.com/other", result)
        for url in result:
            self.assertFalse(any(ord(ch) < 32 for ch in url))

    def test_balanced_profile_deduplicates(self):
        """balanced profile deduplicates after canonicalization."""
        urls = ["https://lovable.dev/a", "https://lovable.dev/a"]
        result = _filter_lovable_storage_urls(urls, "balanced")
        self.assertEqual(result.count("https://lovable.dev/a"), 1)

    def test_balanced_keeps_plausible_urls(self):
        """balanced profile retains valid lovable URLs."""
        urls = ["https://lovable.dev/projects/abc", "https://lovable.app/x"]
        result = _filter_lovable_storage_urls(urls, "balanced")
        self.assertIn("https://lovable.dev/projects/abc", result)

    def test_unknown_profile_returns_all(self):
        """Unknown profile returns all URLs (passthrough fallback)."""
        urls = self._sample_urls()
        result = _filter_lovable_storage_urls(urls, "unknown-profile")
        self.assertEqual(result, urls)

    def test_none_profile_treated_as_normal(self):
        """None profile is treated as 'normal' (passthrough)."""
        urls = ["https://lovable.dev/x"]
        result = _filter_lovable_storage_urls(urls, None)
        self.assertEqual(result, urls)

    def test_empty_list_returns_empty(self):
        """Empty input list returns empty list for any profile."""
        self.assertEqual(_filter_lovable_storage_urls([], "strict"), [])
        self.assertEqual(_filter_lovable_storage_urls([], "balanced"), [])
        self.assertEqual(_filter_lovable_storage_urls([], "normal"), [])


if __name__ == "__main__":
    unittest.main()