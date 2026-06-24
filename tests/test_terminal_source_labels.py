from __future__ import annotations

import unittest

from outputs.terminal_theme import display_source_label


class TerminalSourceLabelTests(unittest.TestCase):
    def test_display_source_label_keeps_timelog_token(self):
        self.assertEqual(display_source_label("TIMELOG.md"), "Worklog (TIMELOG.md)")

    def test_display_source_label_passthrough_for_other_sources(self):
        self.assertEqual(display_source_label("Chrome"), "Chrome")


if __name__ == "__main__":
    unittest.main()
