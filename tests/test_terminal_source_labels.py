from __future__ import annotations

import unittest

from outputs.terminal_theme import WORKLOG_SOURCE, display_source_label


class TerminalSourceLabelTests(unittest.TestCase):
    def test_display_source_label_worklog(self):
        self.assertEqual(display_source_label(WORKLOG_SOURCE), "Worklog")

    def test_display_source_label_github_includes_user(self):
        event = {"source": "GitHub", "_github_user": "mbjorke"}
        self.assertEqual(display_source_label("GitHub", event), "GitHub (mbjorke)")

    def test_display_source_label_passthrough_for_other_sources(self):
        self.assertEqual(display_source_label("Chrome"), "Chrome")


if __name__ == "__main__":
    unittest.main()
