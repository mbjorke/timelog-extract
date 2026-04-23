from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from core.cli import app
from core.projects_lint import lint_projects_payload


class ProjectsLintHelperTests(unittest.TestCase):
    def test_overlap_warns_only_for_enabled_profiles(self):
        payload = {
            "projects": [
                {"name": "A", "customer": "X", "enabled": True, "match_terms": ["shared"]},
                {"name": "B", "enabled": False, "match_terms": ["shared"]},
                {"name": "C", "customer": "Y", "enabled": True, "match_terms": ["shared"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        msgs = "\n".join(w.message for w in warnings)
        self.assertIn("A, C", msgs)
        self.assertNotIn("B", msgs)

    def test_broad_term_warns(self):
        payload = {"projects": [{"name": "Membra", "enabled": True, "match_terms": ["koden"]}]}
        warnings = lint_projects_payload(payload)
        self.assertTrue(any(w.code == "broad-term" for w in warnings))

    def test_overlap_inside_same_customer_is_allowed(self):
        payload = {
            "projects": [
                {"name": "Gittan CLI", "customer": "Gittan", "enabled": True, "match_terms": ["gittan"]},
                {"name": "timelog-extract", "customer": "Gittan", "enabled": True, "match_terms": ["gittan"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertFalse(any(w.code == "overlap-term" for w in warnings))

    def test_overlap_without_customer_namespace_warns(self):
        payload = {
            "projects": [
                {"name": "A", "enabled": True, "match_terms": ["shared"]},
                {"name": "B", "enabled": True, "match_terms": ["shared"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertTrue(any(w.code == "overlap-term" for w in warnings))


class ProjectsLintCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _write_cfg(self, payload: dict) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(json.dumps(payload))
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_projects_lint_pass(self):
        cfg = self._write_cfg({"projects": [{"name": "A", "match_terms": ["alpha"], "enabled": True}]})
        r = self.runner.invoke(app, ["projects-lint", "--config", cfg])
        self.assertEqual(r.exit_code, 0, msg=r.output)
        self.assertIn("PASS", r.output)

    def test_projects_lint_strict_fails_on_warning(self):
        cfg = self._write_cfg(
            {
                "projects": [
                    {"name": "A", "customer": "X", "match_terms": ["shared"], "enabled": True},
                    {"name": "B", "customer": "Y", "match_terms": ["shared"], "enabled": True},
                ]
            }
        )
        r = self.runner.invoke(app, ["projects-lint", "--config", cfg, "--strict"])
        self.assertEqual(r.exit_code, 2, msg=r.output)
        self.assertIn("match_terms overlap", r.output)


if __name__ == "__main__":
    unittest.main()
