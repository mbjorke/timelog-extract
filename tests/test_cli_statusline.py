"""`gittan statusline` prints the same line as scripts/gittan_statusline.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app

_MOCK_CWD = "/fixture/statusline-cwd"


class StatuslineCommandTests(unittest.TestCase):
    def test_cwd_option_prints_the_line_for_that_directory(self):
        with patch("scripts.gittan_statusline.line_for", return_value="gittan: project-alpha") as line_for:
            result = CliRunner().invoke(app, ["statusline", "--cwd", _MOCK_CWD])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(result.output, "gittan: project-alpha\n")
        line_for.assert_called_once_with(_MOCK_CWD)

    def test_without_cwd_reads_the_statusline_stdin_contract(self):
        with patch("scripts.gittan_statusline.line_for", return_value="") as line_for:
            result = CliRunner().invoke(
                app, ["statusline"], input='{"workspace": {"current_dir": "%s"}}' % _MOCK_CWD
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        line_for.assert_called_once_with(_MOCK_CWD)

    def test_errors_print_blank_not_a_traceback(self):
        with patch("core.repo_slug.resolve_path_repo_slug", side_effect=RuntimeError("boom")):
            result = CliRunner().invoke(app, ["statusline", "--cwd", _MOCK_CWD])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(result.output, "\n")


if __name__ == "__main__":
    unittest.main()
