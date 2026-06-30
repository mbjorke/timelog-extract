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
        self.assertTrue(any(w.code == "overlap-term" and w.severity == "warn" for w in warnings))

    def test_overlap_is_review_when_term_matches_multiple_project_names(self):
        payload = {
            "projects": [
                {"name": "blueberry-site", "enabled": True, "match_terms": ["blueberry-site"]},
                {"name": "blueberry-site-admin", "enabled": True, "match_terms": ["blueberry-site"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 1)
        self.assertEqual(overlap[0].severity, "review")

    def test_overlap_warns_when_term_matches_only_one_project_name(self):
        payload = {
            "projects": [
                {"name": "briox-buddy", "enabled": True, "match_terms": ["briox-buddy"]},
                {"name": "timelog-extract", "enabled": True, "match_terms": ["briox-buddy"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        overlap = [w for w in warnings if w.code == "overlap-term"]
        self.assertEqual(len(overlap), 1)
        self.assertEqual(overlap[0].severity, "warn")

    def test_slug_customer_conflict_warns_for_different_customers(self):
        payload = {
            "projects": [
                {"name": "Portal", "customer": "acme.example", "enabled": True,
                 "match_terms": ["acme/portal", "portal dev"]},
                {"name": "portal-dup", "customer": "other.example", "enabled": True,
                 "match_terms": ["acme/portal"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        conflict = [w for w in warnings if w.code == "slug-customer-conflict"]
        self.assertEqual(len(conflict), 1)
        self.assertIn("acme/portal", conflict[0].message)
        self.assertIn("acme.example", conflict[0].message)
        self.assertIn("other.example", conflict[0].message)
        # generic overlap-term is suppressed for the conflicting slug
        self.assertFalse(any(w.code == "overlap-term" and "acme/portal" in w.message for w in warnings))

    def test_slug_same_customer_is_not_a_conflict(self):
        payload = {
            "projects": [
                {"name": "Portal", "customer": "acme.example", "enabled": True,
                 "match_terms": ["acme/portal", "portal dev"]},
                {"name": "Portal API", "customer": "acme.example", "enabled": True,
                 "match_terms": ["acme/portal"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertFalse(any(w.code == "slug-customer-conflict" for w in warnings))

    def test_thin_slug_duplicate_warns_when_richer_profile_covers_slug(self):
        payload = {
            "projects": [
                {"name": "Portal", "customer": "acme.example", "enabled": True,
                 "match_terms": ["portal-repo", "acme.example", "portal dev"]},
                {"name": "portal-repo", "enabled": True, "match_terms": ["portal-repo"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        thin = [w for w in warnings if w.code == "thin-slug-duplicate"]
        self.assertEqual(len(thin), 1)
        self.assertIn("portal-repo", thin[0].message)
        self.assertIn("Portal", thin[0].message)
        # default-bucket note appended (thin profile has no distinct customer)
        self.assertIn("no distinct customer", thin[0].message)

    def test_thin_slug_duplicate_quiet_without_richer_twin(self):
        payload = {
            "projects": [
                {"name": "portal-repo", "customer": "acme.example", "enabled": True,
                 "match_terms": ["portal-repo", "acme.example", "portal dev"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertFalse(any(w.code == "thin-slug-duplicate" for w in warnings))

    def test_repo_path_overlap_warns_across_projects(self):
        payload = {
            "projects": [
                {"name": "A", "enabled": True, "match_terms": ["/Users/me/work/acme"]},
                {"name": "B", "enabled": True, "match_terms": ["/Users/me/work/acme/api"]},
            ]
        }
        warnings = lint_projects_payload(payload)
        msgs = "\n".join(w.message for w in warnings)
        self.assertTrue(any(w.code == "repo-path-overlap" for w in warnings))
        self.assertIn("A", msgs)
        self.assertIn("B", msgs)

    def test_broad_tracked_url_warns_for_multi_tenant_host_only(self):
        payload = {
            "projects": [
                {
                    "name": "Project Alpha",
                    "enabled": True,
                    "match_terms": ["project-alpha"],
                    "tracked_urls": ["gemini.google.com"],
                }
            ]
        }
        warnings = lint_projects_payload(payload)
        broad = [w for w in warnings if w.code == "broad-tracked-url"]
        self.assertEqual(len(broad), 1)
        self.assertIn("gemini.google.com", broad[0].message)

    def test_broad_tracked_url_warns_for_generic_app_prefix(self):
        payload = {
            "projects": [
                {
                    "name": "Project Alpha",
                    "enabled": True,
                    "match_terms": ["project-alpha"],
                    "tracked_urls": ["gemini.google.com/app"],
                }
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertTrue(any(w.code == "broad-tracked-url" for w in warnings))

    def test_specific_chat_tracked_url_does_not_warn(self):
        payload = {
            "projects": [
                {
                    "name": "Project Alpha",
                    "enabled": True,
                    "match_terms": ["project-alpha"],
                    "tracked_urls": ["gemini.google.com/app/abc123", "github.com/org/repo"],
                }
            ]
        }
        warnings = lint_projects_payload(payload)
        self.assertFalse(any(w.code == "broad-tracked-url" for w in warnings))


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
