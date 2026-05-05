"""Tests for projects-audit hit counting and projects-trim removal."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from core.config import load_projects_config_payload, remove_rule_from_project, save_projects_config_payload
from core.projects_audit import (
    build_inline_mapping_suggestions,
    build_projects_audit_payload,
    build_zero_hit_trim_plan_from_audit,
    event_matches_tracked_url,
    is_host_anchored_by_profiles,
)


class ProjectsAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_match_term_hits_substring(self) -> None:
        profiles = [
            {
                "name": "project-alpha",
                "match_terms": ["alpha-token", "shared"],
                "tracked_urls": [],
            }
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "work on alpha-token and more",
                "project": "project-alpha",
            },
            {
                "source": "Chrome",
                "detail": "unrelated",
                "project": "project-alpha",
            },
        ]
        tmp_cfg = self._temp_json()
        self.addCleanup(Path(tmp_cfg).unlink, missing_ok=True)
        payload = build_projects_audit_payload(
            events=events,
            profiles=profiles,
            date_from="2026-05-01",
            date_to="2026-05-02",
            projects_config=tmp_cfg,
            pool="deduped_all_events",
        )
        self.assertEqual(payload["event_count"], 2)
        proj = payload["projects"][0]
        by_val = {r["value"]: r["hits"] for r in proj["match_terms"]}
        self.assertEqual(by_val.get("alpha-token"), 1)
        self.assertEqual(by_val.get("shared"), 0)

    def test_trim_plan_shape_and_zero_hit_rules(self) -> None:
        profiles = [
            {
                "name": "project-beta",
                "match_terms": ["used-term", "unused-term"],
                "tracked_urls": ["tracked.example.com", "stale.example.org"],
            }
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "used-term and https://tracked.example.com/x",
                "project": "project-beta",
            },
        ]
        tmp_cfg = self._temp_json()
        self.addCleanup(Path(tmp_cfg).unlink, missing_ok=True)
        audit = build_projects_audit_payload(
            events=events,
            profiles=profiles,
            date_from="2026-05-01",
            date_to="2026-05-02",
            projects_config=tmp_cfg,
            pool="deduped_all_events",
        )
        plan = build_zero_hit_trim_plan_from_audit(audit)
        self.assertEqual(plan["schema_version"], 1)
        self.assertIn("note", plan)
        self.assertIn("meta", plan)
        self.assertEqual(plan["meta"]["zero_hit_candidates"], 2)
        removals = plan["removals"]
        types_vals = {(r["rule_type"], r["rule_value"]) for r in removals}
        self.assertIn(("match_terms", "unused-term"), types_vals)
        self.assertIn(("tracked_urls", "stale.example.org"), types_vals)
        self.assertNotIn(("match_terms", "used-term"), types_vals)
        self.assertNotIn(("tracked_urls", "tracked.example.com"), types_vals)

    def test_trim_plan_rejects_wrong_audit_schema(self) -> None:
        with self.assertRaises(ValueError):
            build_zero_hit_trim_plan_from_audit({"schema_version": 99, "projects": []})

    def test_projects_audit_write_trim_plan_outputs_schema_v1_json(self) -> None:
        cfg_path = Path(self._temp_json())
        plan_path = Path(self._temp_json())
        self.addCleanup(cfg_path.unlink, missing_ok=True)
        self.addCleanup(plan_path.unlink, missing_ok=True)
        save_projects_config_payload(
            cfg_path,
            {
                "projects": [
                    {
                        "name": "project-beta",
                        "match_terms": ["used-term", "unused-term"],
                        "tracked_urls": ["tracked.example.com", "stale.example.org"],
                    }
                ]
            },
        )
        report = SimpleNamespace(
            all_events=[
                {
                    "source": "Chrome",
                    "detail": "used-term and https://tracked.example.com/x",
                    "project": "project-beta",
                }
            ],
            profiles=load_projects_config_payload(cfg_path).get("projects", []),
        )
        with patch("core.report_service.run_timelog_report", return_value=report):
            result = self.runner.invoke(
                app,
                [
                    "projects-audit",
                    "--projects-config",
                    str(cfg_path),
                    "--from",
                    "2026-05-01",
                    "--to",
                    "2026-05-02",
                    "--write-trim-plan",
                    str(plan_path),
                ],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["meta"]["zero_hit_candidates"], 2)
        removals = {(row["rule_type"], row["rule_value"]) for row in plan["removals"]}
        self.assertIn(("match_terms", "unused-term"), removals)
        self.assertIn(("tracked_urls", "stale.example.org"), removals)

    def test_top_hosts_and_anchored(self) -> None:
        profiles = [
            {
                "name": "acme",
                "match_terms": ["acme.com"],
                "tracked_urls": [],
            }
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "https://acme.com/x and https://other.test/y",
                "project": "acme",
            },
            {
                "source": "Chrome",
                "detail": "see https://other.test/z",
                "project": "acme",
            },
        ]
        tmp_cfg = self._temp_json()
        self.addCleanup(Path(tmp_cfg).unlink, missing_ok=True)
        payload = build_projects_audit_payload(
            events=events,
            profiles=profiles,
            date_from="2026-05-01",
            date_to="2026-05-02",
            projects_config=tmp_cfg,
            pool="deduped_all_events",
            top_hosts_limit=10,
        )
        hosts = {r["host"]: (r["hits"], r["anchored"]) for r in payload["top_hosts"]}
        self.assertEqual(hosts["acme.com"][0], 1)
        self.assertTrue(hosts["acme.com"][1])
        self.assertEqual(hosts["other.test"][0], 2)
        self.assertFalse(hosts["other.test"][1])

    def test_is_host_anchored_tracked_url(self) -> None:
        profiles = [
            {
                "name": "p",
                "match_terms": ["p"],
                "tracked_urls": ["portal.example.org"],
            }
        ]
        self.assertTrue(is_host_anchored_by_profiles("app.portal.example.org", profiles))

    def test_tracked_url_host_match(self) -> None:
        self.assertTrue(
            event_matches_tracked_url("tab https://example.com/path?q=1", "example.com"),
        )
        self.assertFalse(
            event_matches_tracked_url("no urls here", "example.com"),
        )

    def test_remove_rule_from_project(self) -> None:
        payload = {
            "projects": [
                {
                    "name": "Demo",
                    "match_terms": ["keep", "drop-me"],
                    "tracked_urls": ["old.example.test"],
                    "enabled": True,
                }
            ]
        }
        ok = remove_rule_from_project(
            payload,
            project_name="Demo",
            rule_type="match_terms",
            rule_value="drop-me",
        )
        self.assertTrue(ok)
        proj = payload["projects"][0]
        terms = [str(t).lower() for t in proj.get("match_terms", [])]
        self.assertIn("keep", terms)
        self.assertNotIn("drop-me", terms)

        ok2 = remove_rule_from_project(
            payload,
            project_name="Demo",
            rule_type="tracked_urls",
            rule_value="old.example.test",
        )
        self.assertTrue(ok2)
        self.assertEqual(proj.get("tracked_urls"), [])

    def test_inline_mapping_suggestions_bounds_and_words(self) -> None:
        profiles = [
            {
                "name": "project-alpha",
                "match_terms": ["alpha-token", "stale-term"],
                "tracked_urls": [],
            }
        ]
        events = []
        for idx in range(5):
            events.append(
                {
                    "source": "Chrome",
                    "detail": f"https://unmapped.example.dev/page-{idx} alpha-token",
                    "project": "project-alpha",
                }
            )
        suggestions = build_inline_mapping_suggestions(
            events=events,
            profiles=profiles,
            max_candidates=2,
        )
        self.assertGreaterEqual(len(suggestions), 1)
        self.assertLessEqual(len(suggestions), 2)
        self.assertTrue(any("consider adding tracked_urls" in row for row in suggestions))

    def test_inline_mapping_suggestions_quiet_when_low_signal(self) -> None:
        profiles = [{"name": "project-alpha", "match_terms": ["alpha"], "tracked_urls": []}]
        events = [
            {"source": "Chrome", "detail": "alpha only", "project": "project-alpha"},
            {"source": "Chrome", "detail": "alpha only", "project": "project-alpha"},
        ]
        suggestions = build_inline_mapping_suggestions(
            events=events,
            profiles=profiles,
            max_candidates=3,
        )
        self.assertEqual(suggestions, [])

    def test_trim_roundtrip_tmp_file(self) -> None:
        tmp = Path(self._temp_json())
        self.addCleanup(tmp.unlink, missing_ok=True)
        cfg = {
            "projects": [
                {
                    "name": "P",
                    "match_terms": ["a", "b"],
                    "tracked_urls": [],
                    "enabled": True,
                }
            ]
        }
        save_projects_config_payload(tmp, cfg)
        data = load_projects_config_payload(tmp)
        remove_rule_from_project(data, project_name="P", rule_type="match_terms", rule_value="b")
        save_projects_config_payload(tmp, data)
        again = load_projects_config_payload(tmp)
        terms_lower = [str(t).lower() for t in again["projects"][0]["match_terms"]]
        self.assertNotIn("b", terms_lower)
        self.assertIn("a", terms_lower)

    def _temp_json(self) -> str:
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json")
        import os

        os.close(fd)
        return path


if __name__ == "__main__":
    unittest.main()
