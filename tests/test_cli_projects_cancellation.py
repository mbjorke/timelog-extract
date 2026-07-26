"""Integration and UX regression tests for `gittan projects` interactive cancellations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliProjectsCancellationTests(unittest.TestCase):
    def test_projects_command_cancellation_exits_130(self):
        runner = CliRunner()
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "timelog_projects.json"
            # Write a valid starting config
            config_path.write_text(json.dumps({"projects": []}), encoding="utf-8")

            # Patch questionary.select to return None (representing Cancel/Ctrl+C)
            with patch("core.cli_projects.questionary.select") as select_mock:
                select_mock.return_value.ask.return_value = None
                result = runner.invoke(app, ["projects", "--config", str(config_path)])

            self.assertEqual(result.exit_code, 130)
            # Ensure config is unmodified
            data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"projects": []})


if __name__ == "__main__":
    unittest.main()
