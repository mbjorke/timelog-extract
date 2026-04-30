from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from core.cli_date_range import resolve_date_window


class CliDateRangeTests(unittest.TestCase):
    def test_explicit_dates_take_precedence(self):
        date_from, date_to = resolve_date_window(
            date_from=datetime(2026, 4, 1),
            date_to=datetime(2026, 4, 3),
            today=True,
        )
        self.assertEqual((date_from, date_to), ("2026-04-01", "2026-04-03"))

    def test_relative_flags_resolve_iso_window(self):
        with patch("core.cli_date_range.date") as date_cls:
            date_cls.today.return_value = datetime(2026, 4, 30).date()
            date_from, date_to = resolve_date_window(date_from=None, date_to=None, last_week=True)
        self.assertEqual((date_from, date_to), ("2026-04-24", "2026-04-30"))

    def test_prompt_is_used_when_requested(self):
        with patch(
            "core.cli_date_range.prompt_for_timeframe",
            return_value={"date_from": "2026-04-10", "date_to": "2026-04-11"},
        ):
            date_from, date_to = resolve_date_window(date_from=None, date_to=None, prompt_if_missing=True)
        self.assertEqual((date_from, date_to), ("2026-04-10", "2026-04-11"))


if __name__ == "__main__":
    unittest.main()
