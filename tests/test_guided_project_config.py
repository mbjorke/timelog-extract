from __future__ import annotations

import unittest

from core.guided_project_config import build_guided_config_plan


class GuidedProjectConfigTests(unittest.TestCase):
    def test_groups_evidence_candidates_and_config_warnings(self):
        payload = {
            "projects": [
                {"name": "Acme", "enabled": True, "match_terms": ["shared"]},
                {"name": "Other", "enabled": True, "match_terms": ["shared"]},
            ]
        }
        triage_days = [
            {
                "day": "2026-04-21",
                "top_sites": [{"domain": "acme.example.com", "visits": 7, "share": 0.7}],
                "code_repos": [{"provider": "github", "value": "github.com/acme/service-api", "visits": 3}],
                "suggestions": [{"canonical": "Acme"}, {"canonical": "Other"}],
            },
        ]
        plan = build_guided_config_plan(
            projects_payload=payload,
            triage_days=triage_days,
            projects_config="timelog_projects.json",
        )
        self.assertEqual(plan["mode"], "evidence-review")
        self.assertNotIn("update", plan)
        self.assertNotIn("add", plan)
        candidate_types = {item["candidate_type"] for item in plan["candidates"]}
        self.assertEqual(candidate_types, {"domain", "code_repo"})
        self.assertTrue(all(item["requires_user_choice"] for item in plan["candidates"]))
        self.assertTrue(any(w["code"] == "overlap-term" for w in plan["config_warnings"]))

    def test_existing_tracked_urls_are_not_repeated_as_candidates(self):
        payload = {
            "projects": [
                {
                    "name": "Acme",
                    "enabled": True,
                    "tracked_urls": ["acme.example.com", "github.com/acme/service-api"],
                },
            ]
        }
        triage_days = [
            {
                "day": "2026-04-08",
                "top_sites": [{"domain": "acme.example.com", "visits": 5, "share": 1.0}],
                "code_repos": [{"provider": "github", "value": "github.com/acme/service-api", "visits": 5}],
            }
        ]
        plan = build_guided_config_plan(
            projects_payload=payload,
            triage_days=triage_days,
            projects_config="timelog_projects.json",
        )
        self.assertEqual(plan["candidates"], [])

    def test_domain_candidate_is_skipped_when_code_repo_uses_same_host(self):
        payload = {"projects": []}
        triage_days = [
            {
                "day": "2026-04-08",
                "top_sites": [{"domain": "github.com", "visits": 10, "share": 1.0}],
                "code_repos": [{"provider": "github", "value": "github.com/acme/service-api", "visits": 8}],
            }
        ]
        plan = build_guided_config_plan(
            projects_payload=payload,
            triage_days=triage_days,
            projects_config="timelog_projects.json",
        )
        self.assertEqual([item["candidate_type"] for item in plan["candidates"]], ["code_repo"])

    def test_code_repos_are_manual_evidence_candidates(self):
        payload = {"projects": [{"name": "Acme", "enabled": True, "tracked_urls": []}]}
        triage_days = [
            {
                "day": "2026-04-08",
                "code_repos": [{"provider": "github", "value": "github.com/acme/service-api", "visits": 12}],
                "suggestions": [{"canonical": "Acme"}],
            }
        ]
        plan = build_guided_config_plan(
            projects_payload=payload,
            triage_days=triage_days,
            projects_config="timelog_projects.json",
        )
        repo_items = [item for item in plan["candidates"] if item["candidate_type"] == "code_repo"]
        self.assertEqual(len(repo_items), 1)
        self.assertEqual(repo_items[0]["provider"], "github")
        self.assertEqual(repo_items[0]["rule_type"], "tracked_urls")
        self.assertEqual(repo_items[0]["value"], "github.com/acme/service-api")
        self.assertEqual(repo_items[0]["suggested_projects"], ["Acme"])


if __name__ == "__main__":
    unittest.main()
