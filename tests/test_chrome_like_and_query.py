"""Tests for _like_escape() and query_chrome() — Chrome collector security fixes."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collectors.chrome import _like_escape, query_chrome

from chrome_test_support import (
    EPOCH_DELTA_US,
    insert_visit,
    make_chrome_db,
)


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
        self.assertEqual(result, "a\\\\\\%b")

    def test_combined_special_chars(self):
        """All three metacharacters in one string are all escaped."""
        result = _like_escape("a%b_c\\d")
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


class QueryChromeTests(unittest.TestCase):
    """Tests for query_chrome() — especially the params argument."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "History"
        make_chrome_db(self.db_path)

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
        insert_visit(self.db_path, "https://example.com/page", "Example", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(self.db_path, "u.url LIKE '%example.com%'", cu_from, cu_to)
        self.assertEqual(len(rows), 1)
        self.assertIn("example.com", rows[0][1])

    def test_explicit_params_bound_correctly(self):
        """Extra params tuple is appended after the two time-range placeholders."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        insert_visit(self.db_path, "https://example.com/page", "Example", ts)

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
        insert_visit(self.db_path, "https://example.com/50%off", "Discount", ts)
        insert_visit(self.db_path, "https://example.com/regular", "Regular", ts)

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
        insert_visit(self.db_path, "https://example.com/", "Example", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        rows = query_chrome(self.db_path, "u.url LIKE '%example%'", cu_from, cu_to)
        self.assertEqual(rows, [])

    def test_multiple_params_in_or_clause(self):
        """Multiple ? placeholders in an OR clause are all bound correctly."""
        ts = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
        insert_visit(self.db_path, "https://alpha.com/", "Alpha", ts)
        insert_visit(self.db_path, "https://beta.com/", "Beta", ts)
        insert_visit(self.db_path, "https://gamma.com/", "Gamma", ts)

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
        insert_visit(self.db_path, "https://example.com/", "X", ts)

        dt_from = datetime(2026, 4, 10, 11, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc)
        cu_from, cu_to = self._time_range(dt_from, dt_to)

        before = set(os.listdir(tempfile.gettempdir()))
        query_chrome(self.db_path, "1=1", cu_from, cu_to)
        after = set(os.listdir(tempfile.gettempdir()))
        new_files = [f for f in (after - before) if f.endswith(".db")]
        self.assertEqual(new_files, [], "Temp .db files were not cleaned up")


if __name__ == "__main__":
    unittest.main()
