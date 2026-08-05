"""Which hero a run renders, not merely which heroes are registered.

`gittan search` and `gittan report` share one execution path. The hero was
picked from `args.all_events`, but `report` also exposes `--all-events` as a
legacy alias, so that flag identifies an option — not a command.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from outputs.cli_heroes import print_command_hero


class HeroRegistrationTests(unittest.TestCase):
    def test_search_and_report_heroes_are_distinct(self):
        from rich.console import Console

        rendered = {}
        for name in ("report", "search"):
            console = Console(record=True, width=100, force_terminal=False)
            print_command_hero(console, name)
            rendered[name] = console.export_text()

        self.assertIn("Gittan Report", rendered["report"])
        self.assertIn("Gittan Search", rendered["search"])
        self.assertNotEqual(rendered["report"], rendered["search"])


class HeroSelectionTests(unittest.TestCase):
    """print_report must key off command identity, not the shared flag."""

    def _hero_for(self, **arg_fields) -> str:
        args = SimpleNamespace(
            only_project=None,
            only_project_ambiguous=[],
            source_summary=False,
            narrative=False,
            customer=None,
            billable_unit=0.0,
            **arg_fields,
        )
        with patch("outputs.terminal.print_command_hero") as hero_mock:
            from outputs.terminal import print_report

            try:
                print_report(
                    {},            # overall_days
                    {},            # project_reports
                    None,          # screen_time_days
                    [],            # profiles
                    args,
                    None,          # config_path
                    "UTC",         # local_tz
                    [],            # source_order
                    "Uncategorized",
                    lambda *a, **k: 0.0,
                    lambda *a, **k: 0.0,
                )
            except Exception:
                # Rendering the rest of the report needs a full payload; the
                # hero call happens first and is all this test cares about.
                pass
        self.assertTrue(hero_mock.called, "print_report must always render a hero")
        return hero_mock.call_args.args[1]

    def test_search_command_selects_the_search_hero(self):
        self.assertEqual(self._hero_for(command_name="search", all_events=True), "search")

    def test_report_command_selects_the_report_hero(self):
        self.assertEqual(self._hero_for(command_name="report", all_events=False), "report")

    def test_report_with_all_events_alias_keeps_the_report_hero(self):
        self.assertEqual(
            self._hero_for(command_name="report", all_events=True),
            "report",
            "--all-events is an option on report, not a marker for the search command",
        )

    def test_missing_command_name_falls_back_to_report(self):
        self.assertEqual(self._hero_for(all_events=False), "report")

    def test_unknown_command_name_falls_back_to_report_not_status(self):
        """print_command_hero resolves an unknown name to the *status* hero.

        So this path must not forward command_name verbatim: a future command
        reusing these options would silently render Status on a report.
        """
        from outputs.cli_heroes import _HEROES

        self.assertNotIn("review", _HEROES)
        self.assertEqual(self._hero_for(command_name="review", all_events=False), "report")


if __name__ == "__main__":
    unittest.main()
