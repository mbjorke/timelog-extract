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


class IsPlausibleLovableStorageUrlTests(unittest.TestCase):
    """Tests for _is_plausible_lovable_storage_url()."""

    def test_valid_lovable_dev_url(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovable.dev/projects/abc"))

    def test_valid_lovable_app_url(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovable.app/projects/123"))

    def test_valid_lovableproject_com_url(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovableproject.com/"))

    def test_valid_subdomain_lovable_dev(self):
        self.assertTrue(
            _is_plausible_lovable_storage_url("https://id-preview--abc.lovable.dev/path")
        )

    def test_valid_subdomain_lovable_app(self):
        self.assertTrue(
            _is_plausible_lovable_storage_url("https://abc.lovable.app/project/x")
        )

    def test_invalid_unrelated_domain(self):
        self.assertFalse(_is_plausible_lovable_storage_url("https://example.com/lovable.dev"))

    def test_invalid_empty_string(self):
        self.assertFalse(_is_plausible_lovable_storage_url(""))

    def test_invalid_no_host(self):
        self.assertFalse(_is_plausible_lovable_storage_url("/just/a/path"))

    def test_invalid_non_printable_characters(self):
        url = "https://lovable.dev/foo\x01bar"
        self.assertFalse(_is_plausible_lovable_storage_url(url))

    def test_invalid_lovable_in_path_only(self):
        # Host must match, not just path
        self.assertFalse(
            _is_plausible_lovable_storage_url("https://example.com/https://lovable.dev")
        )

    def test_invalid_none_like_empty(self):
        self.assertFalse(_is_plausible_lovable_storage_url(None or ""))


class CanonicalizeLovableStorageUrlTests(unittest.TestCase):
    """Tests for _canonicalize_lovable_storage_url()."""

    def test_valid_url_unchanged(self):
        url = "https://lovable.dev/projects/abc-123"
        self.assertEqual(_canonicalize_lovable_storage_url(url), url)

    def test_truncated_lovableproject_host_recovers(self):
        url = "https://myapp.lovableproject/dashboard"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovableproject.com", result)

    def test_truncated_lov_host_recovers(self):
        url = "https://myapp.lov/dashboard"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_bare_lov_host_recovers(self):
        url = "https://lov/dashboard"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_bare_lovableproject_host_recovers(self):
        url = "https://lovableproject/path"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovableproject.com", result)

    def test_garbage_appended_to_lovable_dev(self):
        url = "https://lovable.devGARBAGE123/foo"
        result = _canonicalize_lovable_storage_url(url)
        self.assertEqual(result, "https://lovable.dev")

    def test_path_contains_lovableproject_com(self):
        url = "https://garbage-host/path/lovableproject.com/foo"
        result = _canonicalize_lovable_storage_url(url)
        self.assertEqual(result, "https://lovableproject.com")

    def test_path_contains_lovable_app(self):
        url = "https://garbage-host/path/lovable.app/foo"
        result = _canonicalize_lovable_storage_url(url)
        self.assertEqual(result, "https://lovable.app")

    def test_non_printable_chars_stripped(self):
        url = "https://lovable.dev\x00/foo"
        result = _canonicalize_lovable_storage_url(url)
        # Non-printable stripped, valid lovable.dev host preserved
        self.assertIn("lovable.dev", result)

    def test_empty_string_returns_empty(self):
        self.assertEqual(_canonicalize_lovable_storage_url(""), "")


class FilterLovableStorageUrlsTests(unittest.TestCase):
    """Tests for _filter_lovable_storage_urls()."""

    GOOD_URLS = [
        "https://lovable.dev/projects/abc",
        "https://lovable.app/dashboard",
        "https://lovableproject.com/",
    ]
    BAD_URLS = [
        "https://lovable.devGARBAGE/path",
        "https://garbage.noisy.lov/fake",
    ]

    def test_normal_profile_returns_all(self):
        urls = self.GOOD_URLS + self.BAD_URLS
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="normal")
        self.assertEqual(result, urls)

    def test_strict_profile_keeps_only_plausible(self):
        urls = self.GOOD_URLS + self.BAD_URLS
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="strict")
        for url in result:
            self.assertTrue(
                _is_plausible_lovable_storage_url(url),
                f"URL should be plausible: {url!r}",
            )
        # All good URLs should be included
        for url in self.GOOD_URLS:
            self.assertIn(url, result)

    def test_balanced_profile_deduplicates(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://lovable.dev/projects/abc",  # duplicate
        ]
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertEqual(len(result), 1)

    def test_balanced_profile_canonicalizes_and_keeps(self):
        urls = [
            "https://lovable.dev/projects/abc",
            "https://garbage.lovableproject/path",  # truncated, salvageable
        ]
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="balanced")
        self.assertGreater(len(result), 0)

    def test_unknown_profile_returns_all(self):
        urls = self.GOOD_URLS + self.BAD_URLS
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="unknown")
        self.assertEqual(result, urls)

    def test_empty_url_list_returns_empty(self):
        self.assertEqual(_filter_lovable_storage_urls([], lovable_noise_profile="strict"), [])

    def test_strict_profile_rejects_non_printable(self):
        urls = ["https://lovable.dev/foo\x01bar"]
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="strict")
        self.assertEqual(result, [])

    def test_normal_profile_none_safe(self):
        # Profile None should fall back to normal
        urls = self.GOOD_URLS
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile=None or "normal")
        self.assertEqual(result, urls)


if __name__ == "__main__":
    unittest.main()