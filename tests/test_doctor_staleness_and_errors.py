from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.cli_doctor_sources_projects import doctor


class DoctorStalenessAndErrorsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.home = self.tmp_path / "home"
        self.home.mkdir()
        self.gittan_dir = self.home / ".gittan"
        self.gittan_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    @patch("rich.console.Console")
    @patch("rich.table.Table")
    @patch("core.cli_doctor_sources_projects.Path.home")
    def test_doctor_reports_stale_worklog(self, mock_home, mock_table_cls, mock_console_cls):
        mock_home.return_value = self.home

        # Create a stale worklog file (last written 8 days ago)
        worklog_path = self.tmp_path / "TIMELOG.md"
        worklog_path.touch()
        stale_time = (datetime.now(timezone.utc) - timedelta(days=8)).timestamp()
        os.utime(worklog_path, (stale_time, stale_time))

        # Create timelog_projects.json pointing to it
        cfg_path = self.gittan_dir / "timelog_projects.json"
        cfg_path.write_text(json.dumps({
            "projects": [
                {"name": "test-repo", "project_id": "test-project", "worklog": str(worklog_path)}
            ]
        }), encoding="utf-8")

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table

        # Run doctor
        with patch("core.cli_doctor_sources_projects.resolve_projects_config_path", return_value=cfg_path):
            doctor(worklog=str(worklog_path))

        # Verify that table.add_row was called with warning/staleness details!
        added_rows = [call.args for call in mock_table.add_row.call_args_list]
        stale_rows = [args for args in added_rows if len(args) >= 3 and "Stale capture" in args[2]]
        self.assertEqual(len(stale_rows), 1)
        self.assertIn("no writes in last 7 days", stale_rows[0][2])

    @patch("rich.console.Console")
    @patch("rich.table.Table")
    @patch("core.cli_doctor_sources_projects.Path.home")
    def test_doctor_reports_capture_errors(self, mock_home, mock_table_cls, mock_console_cls):
        mock_home.return_value = self.home

        # Create capture-errors.jsonl with a mock failure
        err_file = self.gittan_dir / "capture-errors.jsonl"
        err_file.write_text(json.dumps({
            "timestamp": "2026-07-23T02:00:00Z",
            "error": "Permission denied: /unwritable/path",
            "source": "git-commit"
        }) + "\n", encoding="utf-8")

        cfg_path = self.gittan_dir / "timelog_projects.json"
        cfg_path.write_text(json.dumps({}), encoding="utf-8")

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table

        with patch("core.cli_doctor_sources_projects.resolve_projects_config_path", return_value=cfg_path):
            doctor()

        # Verify that table.add_row was called with "Capture errors" and the exact failure message
        added_rows = [call.args for call in mock_table.add_row.call_args_list]
        err_rows = [args for args in added_rows if len(args) >= 3 and args[0] == "Capture errors"]
        self.assertEqual(len(err_rows), 1)
        self.assertIn("Permission denied", err_rows[0][2])


if __name__ == "__main__":
    unittest.main()
