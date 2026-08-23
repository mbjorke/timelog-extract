"""The setup table must answer the question it exists to answer.

`setup-global-timelog` shows where the machine's hooks currently live, then
asks permission to change them. In a narrow terminal every value read
"/Users/me…", so the operator was agreeing to a change to a path the table
declined to show.
"""

import unittest
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from core.global_timelog_machine_setup import _display_path


class DisplayPathTests(unittest.TestCase):
    def test_home_becomes_a_tilde(self):
        home = str(Path.home())
        self.assertEqual(_display_path(home + "/.githooks"), "~/.githooks")
        self.assertEqual(_display_path(home), "~")

    def test_a_sibling_of_home_is_left_alone(self):
        # Only an exact home prefix: "/Users/me-old" is not inside "/Users/me",
        # and rewriting it would point the operator at the wrong directory.
        sibling = str(Path.home()) + "-old/x"
        self.assertEqual(_display_path(sibling), sibling)

    def test_an_unrelated_path_is_unchanged(self):
        self.assertEqual(_display_path("/etc/gitconfig"), "/etc/gitconfig")

    def test_missing_values_render_as_empty(self):
        self.assertEqual(_display_path(None), "")
        self.assertEqual(_display_path("   "), "")

    def test_a_path_survives_a_narrow_terminal_intact(self):
        # Folded, not truncated: the whole path must still be readable at 40
        # columns, because that is where the elision was hiding it.
        home = str(Path.home())
        console = Console(width=40, no_color=True, legacy_windows=False)
        table = Table(title="Current global git status", box=box.ROUNDED)
        table.add_column("Setting", no_wrap=True)
        table.add_column("Current value", overflow="fold")
        table.add_row("Hook file", _display_path(home + "/.githooks/post-commit"))
        with console.capture() as capture:
            console.print(table)
        rendered = capture.get()
        self.assertNotIn("…", rendered)
        # The path may wrap across lines; stripping the frame must restore it.
        flat = "".join(
            line.strip("│ ").replace(" ", "") for line in rendered.splitlines()
        )
        self.assertIn("~/.githooks/post-commit", flat)


if __name__ == "__main__":
    unittest.main()
