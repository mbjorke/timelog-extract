"""GH-342: anchor-plan apply guardrail (kinds + floor + apply filter)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from typer.testing import CliRunner

from core.anchor_plan import build_anchor_plan_from_audit
from core.cli import app
from core.config import load_projects_config_payload, save_projects_config_payload
from core.projects_audit import AUDIT_SCHEMA_VERSION


class AnchorPlanGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def _temp_json(self) -> str:
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json")
        Path(path).write_text("{}", encoding="utf-8")
        import os

        os.close(fd)
        return path

    def test_anchor_plan_from_audit_only_unanchored(self) -> None:
        audit = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "command": "gittan projects-audit",
            "options": {},
            "top_signals": [
                {
                    "kind": "host",
                    "value": "other.test",
                    "hits": 14,
                    "anchored": False,
                    "rule_type": "tracked_urls",
                },
                {
                    "kind": "dir",
                    "value": "project-gamma",
                    "hits": 12,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "branch",
                    "value": "gamma-feature",
                    "hits": 9,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "dir",
                    "value": "project-alpha",
                    "hits": 30,
                    "anchored": True,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "dir",
                    "value": "noise",
                    "hits": 1,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
            ],
        }
        plan = build_anchor_plan_from_audit(
            audit, min_hits=2, include_ephemeral_kinds=True
        )
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["meta"]["anchor_candidates"], 3)
        adds = {
            (a["project_name"], a["rule_type"], a["rule_value"], a["anchor_kind"])
            for a in plan["additions"]
        }
        self.assertIn(("other.test", "tracked_urls", "other.test", "host"), adds)
        self.assertIn(("project-gamma", "match_terms", "project-gamma", "dir"), adds)
        self.assertIn(("gamma-feature", "match_terms", "gamma-feature", "branch"), adds)
        self.assertNotIn(("project-alpha", "match_terms", "project-alpha", "dir"), adds)
        self.assertNotIn(("noise", "match_terms", "noise", "dir"), adds)

    def test_anchor_plan_default_excludes_ephemeral_and_floors_hits(self) -> None:
        audit = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "command": "gittan projects-audit",
            "options": {},
            "top_signals": [
                {
                    "kind": "host",
                    "value": "other.test",
                    "hits": 25,
                    "anchored": False,
                    "rule_type": "tracked_urls",
                },
                {
                    "kind": "dir",
                    "value": "project-gamma",
                    "hits": 22,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "repo",
                    "value": "acme/gamma",
                    "hits": 21,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "branch",
                    "value": "gamma-feature",
                    "hits": 40,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "label",
                    "value": "redesign gamma",
                    "hits": 30,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
                {
                    "kind": "dir",
                    "value": "one-off",
                    "hits": 5,
                    "anchored": False,
                    "rule_type": "match_terms",
                },
            ],
        }
        plan = build_anchor_plan_from_audit(audit)
        self.assertEqual(plan["meta"]["min_hits"], 20)
        self.assertFalse(plan["meta"]["include_ephemeral_kinds"])
        kinds = {a["anchor_kind"] for a in plan["additions"]}
        self.assertEqual(kinds, {"host", "dir", "repo"})
        inv_kinds = {a["anchor_kind"] for a in plan["inventory"]}
        self.assertEqual(inv_kinds, {"branch", "label"})
        self.assertNotIn("one-off", {a["rule_value"] for a in plan["additions"]})
        self.assertIn("branch", plan["meta"]["ephemeral_kinds_excluded_from_apply"])

    def test_anchor_plan_rejects_wrong_audit_schema(self) -> None:
        with self.assertRaises(ValueError):
            build_anchor_plan_from_audit({"schema_version": 99, "top_signals": []})

    def test_projects_anchor_skips_ephemeral_kinds(self) -> None:
        cfg_path = Path(self._temp_json())
        plan_path = Path(self._temp_json())
        self.addCleanup(cfg_path.unlink, missing_ok=True)
        self.addCleanup(plan_path.unlink, missing_ok=True)
        save_projects_config_payload(
            cfg_path,
            {"projects": [{"name": "existing", "match_terms": ["keep"], "tracked_urls": []}]},
        )
        plan = {
            "schema_version": 1,
            "additions": [
                {
                    "project_name": "existing",
                    "rule_type": "match_terms",
                    "rule_value": "project-gamma",
                    "anchor_kind": "dir",
                    "hits": 22,
                },
                {
                    "project_name": "existing",
                    "rule_type": "match_terms",
                    "rule_value": "gamma-feature",
                    "anchor_kind": "branch",
                    "hits": 40,
                },
            ],
        }
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = self.runner.invoke(
            app,
            ["projects-anchor", "--projects-config", str(cfg_path), "-i", str(plan_path)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("skip ephemeral branch", result.output)
        data = load_projects_config_payload(cfg_path)
        proj = next(p for p in data["projects"] if p["name"] == "existing")
        self.assertIn("project-gamma", proj["match_terms"])
        self.assertNotIn("gamma-feature", proj["match_terms"])

    def test_projects_anchor_skips_low_hit_rows(self) -> None:
        cfg_path = Path(self._temp_json())
        plan_path = Path(self._temp_json())
        self.addCleanup(cfg_path.unlink, missing_ok=True)
        self.addCleanup(plan_path.unlink, missing_ok=True)
        save_projects_config_payload(
            cfg_path,
            {"projects": [{"name": "existing", "match_terms": ["keep"], "tracked_urls": []}]},
        )
        plan = {
            "schema_version": 1,
            "additions": [
                {
                    "project_name": "existing",
                    "rule_type": "match_terms",
                    "rule_value": "project-gamma",
                    "anchor_kind": "dir",
                    "hits": 22,
                },
                {
                    "project_name": "existing",
                    "rule_type": "match_terms",
                    "rule_value": "one-off",
                    "anchor_kind": "dir",
                    "hits": 3,
                },
            ],
        }
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = self.runner.invoke(
            app,
            ["projects-anchor", "--projects-config", str(cfg_path), "-i", str(plan_path)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("skip low-hit", result.output)
        data = load_projects_config_payload(cfg_path)
        proj = next(p for p in data["projects"] if p["name"] == "existing")
        self.assertIn("project-gamma", proj["match_terms"])
        self.assertNotIn("one-off", proj["match_terms"])

    def test_projects_anchor_exits_when_only_ephemeral(self) -> None:
        cfg_path = Path(self._temp_json())
        plan_path = Path(self._temp_json())
        self.addCleanup(cfg_path.unlink, missing_ok=True)
        self.addCleanup(plan_path.unlink, missing_ok=True)
        save_projects_config_payload(
            cfg_path,
            {"projects": [{"name": "existing", "match_terms": ["keep"], "tracked_urls": []}]},
        )
        plan = {
            "schema_version": 1,
            "additions": [
                {
                    "project_name": "existing",
                    "rule_type": "match_terms",
                    "rule_value": "gamma-feature",
                    "anchor_kind": "branch",
                    "hits": 40,
                },
            ],
        }
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = self.runner.invoke(
            app,
            ["projects-anchor", "--projects-config", str(cfg_path), "-i", str(plan_path)],
        )
        self.assertEqual(result.exit_code, 1, msg=result.output)
        data = load_projects_config_payload(cfg_path)
        proj = next(p for p in data["projects"] if p["name"] == "existing")
        self.assertEqual(proj["match_terms"], ["keep"])


if __name__ == "__main__":
    unittest.main()
