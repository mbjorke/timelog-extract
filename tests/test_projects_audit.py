"""Tests for projects-audit hit counting and projects-trim removal."""

import json
import unittest
from pathlib import Path

from core.config import load_projects_config_payload, remove_rule_from_project, save_projects_config_payload
from core.projects_audit import (
    build_projects_audit_payload,
    event_matches_tracked_url,
    is_host_anchored_by_profiles,
)


class ProjectsAuditTests(unittest.TestCase):
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
        payload = build_projects_audit_payload(
            events=events,
            profiles=profiles,
            date_from="2026-05-01",
            date_to="2026-05-02",
            projects_config="/tmp/x.json",
            pool="deduped_all_events",
        )
        self.assertEqual(payload["event_count"], 2)
        proj = payload["projects"][0]
        by_val = {r["value"]: r["hits"] for r in proj["match_terms"]}
        self.assertEqual(by_val.get("alpha-token"), 1)
        self.assertEqual(by_val.get("shared"), 0)

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
        payload = build_projects_audit_payload(
            events=events,
            profiles=profiles,
            date_from="2026-05-01",
            date_to="2026-05-02",
            projects_config="/tmp/x.json",
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

    def test_trim_roundtrip_tmp_file(self) -> None:
        tmp = Path(self._temp_json())
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
        tmp.unlink(missing_ok=True)

    def _temp_json(self) -> str:
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json")
        import os

        os.close(fd)
        return path


if __name__ == "__main__":
    unittest.main()
