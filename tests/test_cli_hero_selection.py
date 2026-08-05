from __future__ import annotations

import unittest
from unittest.mock import patch

from core.cli_options import TimelogRunOptions
from outputs.terminal import print_report


class CliHeroSelectionTests(unittest.TestCase):
    @patch("outputs.terminal.print_command_hero")
    @patch("outputs.terminal.Tree")
    def test_hero_selection_for_search_and_report(self, mock_tree, mock_print_hero):
        # 1. Search command setting command_name="search"
        args_search = TimelogRunOptions(
            command_name="search",
            all_events=True,
        )
        print_report(
            overall_days={},
            project_reports={},
            screen_time_days={},
            profiles=[],
            args=args_search,
            config_path=None,
            local_tz=None,
            source_order=[],
            uncategorized="uncategorized",
            session_duration_hours_fn=lambda *a: 0.0,
            billable_total_hours_fn=lambda *a: 0.0,
        )
        mock_print_hero.assert_any_call(unittest.mock.ANY, "search")

        # 2. Report command setting command_name="report" or default
        args_report = TimelogRunOptions(
            command_name="report",
            all_events=False,
        )
        print_report(
            overall_days={},
            project_reports={},
            screen_time_days={},
            profiles=[],
            args=args_report,
            config_path=None,
            local_tz=None,
            source_order=[],
            uncategorized="uncategorized",
            session_duration_hours_fn=lambda *a: 0.0,
            billable_total_hours_fn=lambda *a: 0.0,
        )
        mock_print_hero.assert_any_call(unittest.mock.ANY, "report")

        # 3. Report command with --all-events legacy alias (all_events=True but command_name="report")
        args_legacy = TimelogRunOptions(
            command_name="report",
            all_events=True,
        )
        print_report(
            overall_days={},
            project_reports={},
            screen_time_days={},
            profiles=[],
            args=args_legacy,
            config_path=None,
            local_tz=None,
            source_order=[],
            uncategorized="uncategorized",
            session_duration_hours_fn=lambda *a: 0.0,
            billable_total_hours_fn=lambda *a: 0.0,
        )
        mock_print_hero.assert_any_call(unittest.mock.ANY, "report")

        # 4. Fallback case when command_name is missing/None/empty
        args_fallback = TimelogRunOptions(
            all_events=False,
        )
        # Manually delete command_name attribute to test fallback behavior
        delattr(args_fallback, "command_name")

        print_report(
            overall_days={},
            project_reports={},
            screen_time_days={},
            profiles=[],
            args=args_fallback,
            config_path=None,
            local_tz=None,
            source_order=[],
            uncategorized="uncategorized",
            session_duration_hours_fn=lambda *a: 0.0,
            billable_total_hours_fn=lambda *a: 0.0,
        )
        mock_print_hero.assert_any_call(unittest.mock.ANY, "report")

        # 5. Unknown command name fallback case (e.g. command_name="review")
        args_unknown = TimelogRunOptions(
            command_name="review",
            all_events=False,
        )
        print_report(
            overall_days={},
            project_reports={},
            screen_time_days={},
            profiles=[],
            args=args_unknown,
            config_path=None,
            local_tz=None,
            source_order=[],
            uncategorized="uncategorized",
            session_duration_hours_fn=lambda *a: 0.0,
            billable_total_hours_fn=lambda *a: 0.0,
        )
        mock_print_hero.assert_any_call(unittest.mock.ANY, "report")

    def test_search_and_report_heroes_are_distinct(self):
        from outputs.cli_heroes import _HEROES
        self.assertIn("search", _HEROES)
        self.assertIn("report", _HEROES)
        self.assertNotEqual(_HEROES["search"], _HEROES["report"])


if __name__ == "__main__":
    unittest.main()
