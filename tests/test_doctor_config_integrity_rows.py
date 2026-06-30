from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rich.table import Table

from core.doctor_projects_config_rows import add_config_integrity_rows


def _write_config(payload: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(payload, tmp)
    tmp.close()
    return Path(tmp.name)


class DoctorConfigIntegrityRowTests(unittest.TestCase):
    def _table(self) -> Table:
        table = Table()
        table.add_column("Source / Path")
        table.add_column("Status")
        table.add_column("Details")
        return table

    def test_integrity_rows_added_for_conflict_and_thin_duplicate(self):
        config = _write_config(
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
        add_config_integrity_rows(table, config, warn_icon="!", style_muted="dim")
        # slug-customer-conflict + thin-slug-duplicate => at least two rows
        self.assertGreaterEqual(table.row_count, 2)

    def test_no_rows_for_clean_config(self):
        config = _write_config(
            {
                "projects": [
                    {"name": "Portal", "customer": "acme.example", "enabled": True,
                     "match_terms": ["acme/portal", "portal dev"]},
                ]
            }
        )
        table = self._table()
        add_config_integrity_rows(table, config, warn_icon="!", style_muted="dim")
        self.assertEqual(table.row_count, 0)


if __name__ == "__main__":
    unittest.main()
