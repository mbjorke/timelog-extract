from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rich.table import Table

from core.doctor_projects_config_rows import add_projects_config_lint_rows


class DoctorConfigIntegrityRowTests(unittest.TestCase):
    def _write_config(self, payload: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, tmp)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def _table(self) -> Table:
        table = Table()
        table.add_column("Source / Path")
        table.add_column("Status")
        table.add_column("Details")
        return table

    def test_integrity_rows_added_for_conflict_and_thin_duplicate(self):
        config = self._write_config(
            {
                "projects": [
                    {"name": "Portal", "customer": "acme.example", "enabled": True,
                     "match_terms": ["acme/portal", "portal-repo", "portal dev"]},
                    {"name": "portal-dup", "customer": "other.example", "enabled": True,
                     "match_terms": ["acme/portal"]},
                    {"name": "portal-repo", "enabled": True, "match_terms": ["portal-repo"]},
                ]
            }
        )
        table = self._table()
        add_projects_config_lint_rows(table, config, warn_icon="!", style_muted="dim")
        # slug-customer-conflict + thin-slug-duplicate => at least two rows
        self.assertGreaterEqual(table.row_count, 2)

    def test_no_rows_for_clean_config(self):
        config = self._write_config(
            {
                "projects": [
                    {"name": "Portal", "customer": "acme.example", "enabled": True,
                     "match_terms": ["acme/portal", "portal dev"]},
                ]
            }
        )
        table = self._table()
        add_projects_config_lint_rows(table, config, warn_icon="!", style_muted="dim")
        self.assertEqual(table.row_count, 0)

    def test_malformed_config_is_skipped_not_raised(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write("{ this is not valid json")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        table = self._table()
        # malformed JSON (a ValueError subclass) is swallowed → no rows, no raise
        add_projects_config_lint_rows(table, Path(tmp.name), warn_icon="!", style_muted="dim")
        self.assertEqual(table.row_count, 0)

    def test_missing_config_is_skipped_not_raised(self):
        table = self._table()
        # unreadable path (OSError) is swallowed → no rows, no raise
        add_projects_config_lint_rows(
            table, Path("/nonexistent/gittan-projects.json"), warn_icon="!", style_muted="dim"
        )
        self.assertEqual(table.row_count, 0)


if __name__ == "__main__":
    unittest.main()
