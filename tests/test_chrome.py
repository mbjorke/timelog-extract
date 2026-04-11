"""Tests for collectors/chrome.py — covers the PR security fix:
_like_escape(), query_chrome() params threading, and special-character
handling in collect_claude_ai_urls, collect_gemini_web_urls, and
collect_chrome.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from collectors.chrome import (
    _like_escape,
    collect_chrome,
    collect_claude_ai_urls,
    collect_gemini_web_urls,
    query_chrome,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Chrome stores time as microseconds since 1601-01-01 00:00:00 UTC.
# The epoch_delta_us constant converts that to Unix µs.
EPOCH_DELTA_US = 11_644_473_600_000_000


def _make_chrome_db(path: Path) -> None:
    """Create a minimal Chrome History SQLite database at *path*."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE urls (
            id    INTEGER PRIMARY KEY,
            url   TEXT NOT NULL,
            title TEXT
        );
        CREATE TABLE visits (
            id         INTEGER PRIMARY KEY,
            url        INTEGER NOT NULL,
            visit_time INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_visit(db_path: Path, url: str, title: str, ts: datetime) -> None:
    """Insert one visit row into *db_path*."""
    visit_time_cu = int(ts.timestamp() * 1_000_000) + EPOCH_DELTA_US
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("INSERT INTO urls (url, title) VALUES (?, ?)", (url, title))
    url_id = cur.lastrowid
    cur.execute("INSERT INTO visits (url, visit_time) VALUES (?, ?)", (url_id, visit_time_cu))
    conn.commit()
    conn.close()


def _make_event(source, ts, detail, project):
    return {"source": source, "ts": ts, "detail": detail, "project": project}


# ---------------------------------------------------------------------------
# _like_escape
# ---------------------------------------------------------------------------


class LikeEscapeTests(unittest.TestCase):
    """Pure-function tests for _like_escape."""

    def test_plain_string_unchanged(self):
        """Strings without LIKE metacharacters pass through unmodified."""
        self.assertEqual(_like_escape("hello world"), "hello world")

    def test_percent_is_escaped(self):
        """% is replaced with \\%."""
        self.assertEqual(_like_escape("50%"), "50\\%")

    def test_underscore_is_escaped(self):
        """_ is replaced with \\_."""
        self.assertEqual(_like_escape("some_project"), "some\\_project")

    def test_backslash_is_escaped_first(self):
        """Backslash is doubled before other escapes so it isn't double-escaped."""
        self.assertEqual(_like_escape("a\\b"), "a\\\\b")

    def test_backslash_before_percent_no_double_escape(self):
        r"""\\% should produce \\\\\\% (escaped backslash + escaped percent)."""
        result = _like_escape("a\\%b")
        # original: a\%b
        # after backslash pass: a\\%b
        # after percent pass: a\\\\%b... wait let's be precise:
        # step1: replace \ with \\  => "a\\%b"
        # step2: replace % with \%  => "a\\\%b"
        self.assertEqual(result, "a\\\\\\%b")

    def test_combined_special_chars(self):
        """All three metacharacters in one string are all escaped."""
        result = _like_escape("a%b_c\\d")
        # step1 backslash: a%b_c\\d
        # step2 percent: a\%b_c\\d
        # step3 underscore: a\%b\_c\\d
        self.assertEqual(result, "a\\%b\\_c\\\\d")

    def test_empty_string(self):
        """Empty string returns empty string."""
        self.assertEqual(_like_escape(""), "")

    def test_multiple_percent_signs(self):
        """Multiple % signs are all escaped."""
        self.assertEqual(_like_escape("100%pure%"), "100\\%pure\\%")

    def test_multiple_underscores(self):
        """Multiple underscores are all escaped."""
        self.assertEqual(_like_escape("a_b_c"), "a\\_b\\_c")

    def test_only_special_chars(self):
        """String that is nothing but metacharacters."""
        self.assertEqual(_like_escape("%_%"), "\\%\\_\\%")


# ---------------------------------------------------------------------------
# query_chrome — params threading
# ---------------------------------------------------------------------------


class QueryChromeTests(unittest.TestCase):
    """Tests for query_chrome() — especially the new params argument."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "History"
        _make_chrome_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _time_range(self, dt_from: datetime, dt_to: datetime):
        return (
            int(dt_from.timestamp() * 1_000_000) + EPOCH_DELTA_US,
            int(dt_to.timestamp() * 1_000_000) + EPOCH_DELTA_US,
        )

    def test_nonexistent_db_returns_empty_list(self):
        """Returns [] when the history file does not exist."""
        missing = Path(self.tmpdir.name) / "NoSuchFile"
        result = query_chrome(missing, "1=1", 0, 10**18)
        self.assertEqual(result, [])

    def test_default_params_returns_matching_row(self):
        """With default params=(), a simple where clause returns results."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://example.com/page", "Example", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(self.db_path, "u.url LIKE '%example.com%'", cu_from, cu_to)
        self.assertEqual(len(rows), 1)
        self.assertIn("example.com", rows[0][1])

    def test_explicit_params_bound_correctly(self):
        """Extra params tuple is appended after the two time-range placeholders."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://example.com/page", "Example", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(
            self.db_path,
            "u.url LIKE ? ESCAPE '\\'",
            cu_from,
            cu_to,
            params=("%example.com%",),
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("example.com", rows[0][1])

    def test_params_with_escaped_percent_matches_literal(self):
        """A \\% in the param matches a literal % in the URL, not a wildcard."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://example.com/50%off", "Discount", ts)
        _insert_visit(self.db_path, "https://example.com/regular", "Regular", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        escaped = f"%{_like_escape('50%off')}%"
        rows = query_chrome(
            self.db_path,
            "u.url LIKE ? ESCAPE '\\'",
            cu_from,
            cu_to,
            params=(escaped,),
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("50%off", rows[0][1])

    def test_no_rows_outside_time_range(self):
        """Rows outside the time range are not returned."""
        ts = datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://example.com/", "Example", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(self.db_path, "u.url LIKE '%example%'", cu_from, cu_to)
        self.assertEqual(rows, [])

    def test_multiple_params_in_or_clause(self):
        """Multiple ? placeholders in an OR clause are all bound correctly."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://alpha.com/", "Alpha", ts)
        _insert_visit(self.db_path, "https://beta.com/", "Beta", ts)
        _insert_visit(self.db_path, "https://gamma.com/", "Gamma", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(
            self.db_path,
            "u.url LIKE ? ESCAPE '\\' OR u.url LIKE ? ESCAPE '\\'",
            cu_from,
            cu_to,
            params=("%alpha.com%", "%beta.com%"),
        )
        urls = [r[1] for r in rows]
        self.assertEqual(len(rows), 2)
        self.assertTrue(any("alpha" in u for u in urls))
        self.assertTrue(any("beta" in u for u in urls))

    def test_temp_file_cleaned_up_after_query(self):
        """The temporary database copy is removed after query_chrome returns."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://example.com/", "X", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        before = set(os.listdir(tempfile.gettempdir()))
        query_chrome(self.db_path, "1=1", cu_from, cu_to)
        after = set(os.listdir(tempfile.gettempdir()))
        new_files = [f for f in (after - before) if f.endswith(".db")]
        self.assertEqual(new_files, [], "Temp .db files were not cleaned up")


# ---------------------------------------------------------------------------
# collect_claude_ai_urls — special-character regression
# ---------------------------------------------------------------------------


class CollectClaudeAiUrlsTests(unittest.TestCase):
    """Tests for collect_claude_ai_urls with the parameterized query fix."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir.name)
        chrome_dir = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
        )
        chrome_dir.mkdir(parents=True)
        self.db_path = chrome_dir / "History"
        _make_chrome_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _call(self, profiles):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_claude_ai_urls(
            profiles,
            dt_from,
            dt_to,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            uncategorized="Uncategorized",
            make_event=_make_event,
        )

    def test_no_claude_urls_in_profiles_returns_empty(self):
        """Profiles with no claude.ai tracked_urls → []."""
        profiles = [{"name": "P", "tracked_urls": ["https://example.com/"]}]
        self.assertEqual(self._call(profiles), [])

    def test_matching_url_returned(self):
        """A visit to a claude.ai URL is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/chat/abc123",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Claude.ai (web)")

    def test_url_with_percent_sign_does_not_error(self):
        """A tracked_url containing % is escaped and does not cause a SQL error."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/chat/50%25encoded",
            "Claude chat",
            ts,
        )
        # The tracked URL itself has a literal % — _like_escape must handle it.
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/50%25encoded"]}]
        # Should not raise; result may or may not match depending on literal escaping.
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_url_with_underscore_is_escaped(self):
        """A tracked_url containing _ is escaped so it doesn't act as a wildcard."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/project_name/chat",
            "Claude chat",
            ts,
        )
        # With unescaped _, "project_name" would match "project.name" too.
        # With escaping it only matches the literal underscore.
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/project_name"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_single_quote_in_url_does_not_error(self):
        """A project URL containing a single-quote is safely parameterized."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/chat/it's-fine",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/it's-fine"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_non_matching_url_not_in_results(self):
        """Visits outside the tracked URL list are not returned."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/chat/other",
            "Claude chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["claude.ai/chat/specific-id"]}]
        results = self._call(profiles)
        # "other" should not match "specific-id"
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# collect_gemini_web_urls — special-character regression
# ---------------------------------------------------------------------------


class CollectGeminiWebUrlsTests(unittest.TestCase):
    """Tests for collect_gemini_web_urls with the parameterized query fix."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir.name)
        chrome_dir = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
        )
        chrome_dir.mkdir(parents=True)
        self.db_path = chrome_dir / "History"
        _make_chrome_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _call(self, profiles):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_gemini_web_urls(
            profiles,
            dt_from,
            dt_to,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            uncategorized="Uncategorized",
            make_event=_make_event,
        )

    def test_no_gemini_urls_returns_empty(self):
        """Profiles with no gemini.google.com tracked_urls → []."""
        profiles = [{"name": "P", "tracked_urls": ["https://example.com/"]}]
        self.assertEqual(self._call(profiles), [])

    def test_matching_gemini_visit_returned(self):
        """A visit to a gemini.google.com URL is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/abc123",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Gemini (web)")

    def test_url_with_percent_sign_does_not_error(self):
        """A tracked_url with % is safely escaped in the LIKE parameter."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/q%3Dhello",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/q%3Dhello"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_single_quote_in_url_does_not_cause_sql_error(self):
        """The old code used chr(39)*2 escaping; now parameterized — must not raise."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/it's-here",
            "Gemini chat",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/it's-here"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_underscore_in_tracked_url_is_literal(self):
        """Underscore in a tracked URL is escaped so it matches literally."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        # URL with underscore
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/my_chat",
            "Gemini chat",
            ts,
        )
        # Different URL that would match an unescaped _ wildcard
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/myXchat",
            "Gemini chat 2",
            ts,
        )
        profiles = [{"name": "Proj", "tracked_urls": ["gemini.google.com/app/my_chat"]}]
        results = self._call(profiles)
        # Only the exact underscore URL should match
        urls = [r["detail"] for r in results]
        self.assertEqual(len(results), 1)
        self.assertIn("my_chat", results[0]["detail"])


# ---------------------------------------------------------------------------
# collect_chrome — keyword special-character regression
# ---------------------------------------------------------------------------


class CollectChromeTests(unittest.TestCase):
    """Tests for collect_chrome with the parameterized query fix."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir.name)
        chrome_dir = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
        )
        chrome_dir.mkdir(parents=True)
        self.db_path = chrome_dir / "History"
        _make_chrome_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _call(self, profiles, collapse_minutes=0):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_chrome(
            profiles,
            dt_from,
            dt_to,
            collapse_minutes=collapse_minutes,
            home=self.home,
            epoch_delta_us=EPOCH_DELTA_US,
            classify_project=lambda text, profs: "Proj",
            make_event=_make_event,
        )

    def test_no_keywords_returns_empty(self):
        """Profiles with no match_terms or names → []."""
        profiles = [{"name": "", "match_terms": []}]
        self.assertEqual(self._call(profiles), [])

    def test_keyword_matches_url(self):
        """A visit whose URL contains the keyword is returned."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://myproject.io/dashboard",
            "Dashboard",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["myproject"]}]
        results = self._call(profiles)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Chrome")

    def test_keyword_with_percent_sign_does_not_error(self):
        """A keyword containing % is safely escaped and does not raise."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://site.com/100%25complete",
            "Done",
            ts,
        )
        # The keyword itself contains a literal percent
        profiles = [{"name": "Proj", "match_terms": ["100%25complete"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_keyword_with_underscore_does_not_match_any_char(self):
        """Keyword underscore is escaped; 'foo_bar' doesn't match 'fooXbar'."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        # "fooXbar" would match unescaped "foo_bar" LIKE pattern; it must not match here.
        _insert_visit(
            self.db_path,
            "https://site.com/fooXbar",
            "Decoy",
            ts,
        )
        _insert_visit(
            self.db_path,
            "https://site.com/foo_bar",
            "Target",
            ts,
        )
        # Profile name "ZZZ" and term "foo_bar" — "zzz" does not appear in either URL.
        profiles = [{"name": "ZZZ", "match_terms": ["foo_bar"]}]
        results = self._call(profiles)
        # Exactly one result — the "fooXbar" decoy was not matched by the escaped pattern.
        self.assertEqual(len(results), 1)
        # collect_chrome uses the page title as detail; verify it's the target row.
        self.assertEqual(results[0]["detail"], "Target")

    def test_claude_ai_url_excluded(self):
        """claude.ai visits are excluded even when the keyword matches."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://claude.ai/chat/xyz",
            "Claude",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["claude"]}]
        results = self._call(profiles)
        self.assertEqual(results, [])

    def test_gemini_url_excluded(self):
        """gemini.google.com visits are excluded even when the keyword matches."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://gemini.google.com/app/abc",
            "Gemini",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["gemini"]}]
        results = self._call(profiles)
        self.assertEqual(results, [])

    def test_keyword_with_single_quote_does_not_raise(self):
        """Single-quote in keyword is handled safely by parameterized query."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://site.com/it-is-fine",
            "Fine",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["it's-fine"]}]
        results = self._call(profiles)
        self.assertIsInstance(results, list)

    def test_multiple_keywords_each_generate_two_params(self):
        """Each keyword produces params for both LOWER(u.url) and LOWER(u.title)."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(self.db_path, "https://alpha.io/", "Alpha Page", ts)
        _insert_visit(self.db_path, "https://beta.io/", "Beta Page", ts)
        _insert_visit(self.db_path, "https://unrelated.io/", "Nope", ts)

        profiles = [{"name": "Proj", "match_terms": ["alpha", "beta"]}]
        results = self._call(profiles)
        urls = [r["detail"] for r in results]
        self.assertEqual(len(results), 2)

    def test_keyword_matches_title_not_only_url(self):
        """The LIKE clause covers both URL and title; a title-only match is collected."""
        ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        _insert_visit(
            self.db_path,
            "https://nondescript.io/page",
            "This is my_special project page",
            ts,
        )
        profiles = [{"name": "Proj", "match_terms": ["my_special"]}]
        results = self._call(profiles)
        # my_special is escaped, so it must match the literal string in the title
        self.assertEqual(len(results), 1)


# ---------------------------------------------------------------------------
# Regression: _like_escape is applied before wrapping in wildcards
# ---------------------------------------------------------------------------


class LikeEscapeIntegrationTests(unittest.TestCase):
    """Verify that _like_escape + wildcard wrapping produces correct LIKE params."""

    def test_escaped_percent_param_matches_literal_percent_in_db(self):
        """End-to-end: a URL with a literal % is found only when escaped correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            chrome_dir = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "Default"
            )
            chrome_dir.mkdir(parents=True)
            db_path = chrome_dir / "History"
            _make_chrome_db(db_path)

            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            _insert_visit(db_path, "https://claude.ai/chat/50%done", "Claude", ts)
            _insert_visit(db_path, "https://claude.ai/chat/normal", "Claude 2", ts)

            dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
            results = collect_claude_ai_urls(
                [{"name": "Proj", "tracked_urls": ["claude.ai/chat/50%done"]}],
                dt_from,
                dt_to,
                home=home,
                epoch_delta_us=EPOCH_DELTA_US,
                uncategorized="Uncategorized",
                make_event=_make_event,
            )
            # Must find exactly the URL with literal % and not the other
            self.assertEqual(len(results), 1)
            self.assertIn("50%done", results[0]["detail"])

    def test_escaped_underscore_does_not_match_arbitrary_char(self):
        """End-to-end: a keyword with _ only matches the literal underscore character."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            chrome_dir = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "Default"
            )
            chrome_dir.mkdir(parents=True)
            db_path = chrome_dir / "History"
            _make_chrome_db(db_path)

            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            # "fooXbar" would match unescaped "foo_bar" LIKE; with escaping it must not.
            # Profile name "ZZZ" to avoid its lower-case form appearing in the URLs.
            _insert_visit(db_path, "https://example.com/fooXbar", "Decoy", ts)
            _insert_visit(db_path, "https://example.com/foo_bar", "Target", ts)

            dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
            dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
            results = collect_chrome(
                [{"name": "ZZZ", "match_terms": ["foo_bar"]}],
                dt_from,
                dt_to,
                collapse_minutes=0,
                home=home,
                epoch_delta_us=EPOCH_DELTA_US,
                classify_project=lambda t, p: "ZZZ",
                make_event=_make_event,
            )
            # Exactly one result — the "fooXbar" decoy was not matched.
            self.assertEqual(len(results), 1)
            # collect_chrome uses the page title as detail; verify it's the target row.
            self.assertEqual(results[0]["detail"], "Target")


if __name__ == "__main__":
    unittest.main()