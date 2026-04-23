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


class ProjectsLintPayloadEdgeCasesTests(unittest.TestCase):
    """Additional edge cases for lint_projects_payload."""

    def test_no_projects_returns_no_warnings(self):
        warnings = lint_projects_payload({"projects": []})
        self.assertEqual(warnings, [])

    def test_empty_payload_returns_no_warnings(self):
        warnings = lint_projects_payload({})
        self.assertEqual(warnings, [])

    def test_non_dict_project_entries_are_skipped(self):
        """Non-dict entries in projects list should not crash the linter."""
        payload = {"projects": [None, "string_entry", {"name": "ValidProject", "enabled": True, "match_terms": []}]}
        warnings = lint_projects_payload(payload)
        # Should complete without raising
        self.assertIsInstance(warnings, list)

    def test_disabled_project_not_included_in_broad_term_check(self):
        """High-risk term in a disabled project should produce no warning."""
        payload = {
            "projects": [
                {"name": "DisabledProject", "enabled": False, "match_terms": ["koden"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertFalse(any(w.code == "broad-term" for w in warnings))

    def test_multiple_high_risk_terms_produce_multiple_warnings(self):
        """Each high-risk term in a project should generate a separate broad-term warning."""
        payload = {
            "projects": [
                {"name": "Membra", "enabled": True, "match_terms": ["koden", "formulär"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        broad_warns = [w for w in warnings if w.code == "broad-term"]
        self.assertEqual(len(broad_warns), 2)

    def test_lint_warning_has_code_and_message(self):
        """LintWarning dataclass must have code and message attributes."""
        payload = {
            "projects": [
                {"name": "A", "customer": "X", "enabled": True, "match_terms": ["shared"]},
                {"name": "B", "customer": "Y", "enabled": True, "match_terms": ["shared"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        for w in warnings:
            self.assertTrue(hasattr(w, "code"))
            self.assertTrue(hasattr(w, "message"))
            self.assertIsInstance(w.code, str)
            self.assertIsInstance(w.message, str)

    def test_overlap_term_message_names_projects(self):
        """The overlap-term message must name the projects involved."""
        payload = {
            "projects": [
                {"name": "ProjectAlpha", "customer": "X", "enabled": True, "match_terms": ["shared-term"]},
                {"name": "ProjectBeta", "customer": "Y", "enabled": True, "match_terms": ["shared-term"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertTrue(any("ProjectAlpha" in w.message for w in overlap))
        self.assertTrue(any("ProjectBeta" in w.message for w in overlap))

    def test_empty_match_terms_no_warnings(self):
        payload = {
            "projects": [
                {"name": "A", "enabled": True, "match_terms": []},
                {"name": "B", "enabled": True, "match_terms": []},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertEqual(warnings, [])

    def test_whitespace_only_match_term_is_skipped(self):
        payload = {"projects": [{"name": "A", "enabled": True, "match_terms": ["  ", ""]}]}
        warnings = lint_projects_payload(payload)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()