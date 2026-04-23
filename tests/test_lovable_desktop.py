"""Tests for Lovable Desktop (Electron) history discovery."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from collectors.lovable_desktop import (
    _canonicalize_lovable_storage_url,
    _filter_lovable_storage_urls,
    _extract_lovable_urls,
    _is_plausible_lovable_storage_url,
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

    def test_filter_lovable_storage_urls_normal_returns_all_unchanged(self):
        """Normal profile passes all URLs through without filtering."""
        urls = [
            "https://lovable.dev/projects/abc",
            "https://lovable.devNOISE",
            "https://garbage.example.com/lovable",
        ]
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="normal")
        self.assertEqual(result, urls)

    def test_filter_lovable_storage_urls_unknown_profile_returns_all(self):
        """Unknown profile name falls through to return urls unchanged."""
        urls = ["https://lovable.dev/x", "https://lovable.devNOISE"]
        result = _filter_lovable_storage_urls(urls, lovable_noise_profile="unknown-profile")
        self.assertEqual(result, urls)

    def test_filter_lovable_storage_urls_empty_list(self):
        for profile in ("normal", "balanced", "strict"):
            result = _filter_lovable_storage_urls([], lovable_noise_profile=profile)
            self.assertEqual(result, [], msg=f"profile={profile}")


class IsPlausibleLovableStorageUrlTests(unittest.TestCase):
    """Direct unit tests for _is_plausible_lovable_storage_url()."""

    def test_valid_lovable_dev_url(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovable.dev/projects/abc"))

    def test_valid_lovable_app_subdomain(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://id-preview--abc.lovable.app/path"))

    def test_valid_lovableproject_com(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://x.lovableproject.com/hello"))

    def test_invalid_wrong_domain(self):
        self.assertFalse(_is_plausible_lovable_storage_url("https://lovable.devNOISE"))

    def test_invalid_empty_host(self):
        self.assertFalse(_is_plausible_lovable_storage_url("https:///path"))

    def test_invalid_garbage_appended_to_host(self):
        self.assertFalse(_is_plausible_lovable_storage_url("https://lovable.dev116cS"))

    def test_invalid_non_printable_chars(self):
        url = "https://lovable.dev/\x01path"
        self.assertFalse(_is_plausible_lovable_storage_url(url))

    def test_invalid_empty_string(self):
        self.assertFalse(_is_plausible_lovable_storage_url(""))

    def test_valid_lovable_dev_with_path_and_query(self):
        self.assertTrue(_is_plausible_lovable_storage_url("https://lovable.dev/projects/abc?foo=bar"))

    def test_invalid_lovableproject_without_tld(self):
        """lovableproject (without .com) is not a plausible host."""
        self.assertFalse(_is_plausible_lovable_storage_url("https://lovableproject/path"))


class CanonicalizeLovableStorageUrlTests(unittest.TestCase):
    """Direct unit tests for _canonicalize_lovable_storage_url()."""

    def test_already_valid_url_unchanged(self):
        url = "https://lovable.dev/projects/abc"
        self.assertEqual(_canonicalize_lovable_storage_url(url), url)

    def test_truncated_lovableproject_gets_com(self):
        url = "https://uuid.lovableproject."
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovableproject.com", result)

    def test_truncated_lov_gets_lovable_app(self):
        url = "https://id-preview--uuid.lov"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_host_lov_becomes_lovable_app(self):
        url = "https://lov/path"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_host_lovableproject_becomes_com(self):
        url = "https://lovableproject/path"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovableproject.com", result)

    def test_lovable_dev_with_garbage_appended(self):
        url = "https://lovable.devNOISEGARBAGE"
        result = _canonicalize_lovable_storage_url(url)
        self.assertEqual(result, "https://lovable.dev")

    def test_non_printable_chars_stripped(self):
        url = "https://\x01lovable.dev/path"
        result = _canonicalize_lovable_storage_url(url)
        # Should not contain non-printable chars
        self.assertTrue(all(ord(ch) >= 32 for ch in result))

    def test_path_contains_lovable_app(self):
        """When host is broken but path contains lovable.app, salvage it."""
        url = "https://brokenhost/lovable.app/projects"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovable.app", result)

    def test_path_contains_lovableproject_com(self):
        """When host is broken but path contains lovableproject.com, salvage it."""
        url = "https://brokenhost/lovableproject.com/projects"
        result = _canonicalize_lovable_storage_url(url)
        self.assertIn("lovableproject.com", result)

    def test_empty_string_returns_empty_or_unchanged(self):
        result = _canonicalize_lovable_storage_url("")
        self.assertEqual(result, "")


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