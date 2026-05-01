from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from core.cli_triage_domains import build_domain_project_candidates, _candidate_choice


class TriageDomainsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def _config_path(self) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(json.dumps({"projects": [{"name": "Demo", "match_terms": [], "tracked_urls": []}]}))
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_build_domain_candidates_prefers_dominant_project(self):
        plan = {
            "days": [
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                },
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                },
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Other",
                    "top_sites": [{"domain": "demo.test"}],
                },
            ],
            "domain_project_counts": {},
        }
        out = build_domain_project_candidates(plan, min_votes=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["domain"], "demo.test")
        self.assertEqual(out[0]["project_name"], "Demo")
        self.assertEqual(out[0]["votes"], 2)

    def test_build_domain_candidates_merges_www_and_bare_host(self):
        plan = {
            "days": [
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Alpha",
                    "top_sites": [{"domain": "www.merge.test"}],
                },
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Alpha",
                    "top_sites": [{"domain": "merge.test"}],
                },
            ],
            "domain_project_counts": {},
        }
        out = build_domain_project_candidates(plan, min_votes=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["domain"], "merge.test")
        self.assertEqual(out[0]["votes"], 2)

    def test_history_dominant_uses_merged_domain_project_counts(self):
        plan = {
            "days": [
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "hist.test"}],
                }
            ],
            "domain_project_counts": {
                "www.hist.test": [{"project": "Demo", "events": 4}],
                "hist.test": [{"project": "Demo", "events": 3}],
            },
        }
        out = build_domain_project_candidates(plan, min_votes=5)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["history_dominant"])

    def test_ambiguous_split_when_projects_nearly_tied(self):
        plan = {
            "days": [
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "A",
                    "top_sites": [{"domain": "tie.test"}],
                },
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "B",
                    "top_sites": [{"domain": "tie.test"}],
                },
            ],
            "domain_project_counts": {},
        }
        out = build_domain_project_candidates(plan, min_votes=1)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["ambiguous_split"])
        choice = _candidate_choice(out[0])
        self.assertIn("ambiguous", choice.title)

    def test_triage_domains_happy_path_applies_after_confirm(self):
        cfg = self._config_path()
        plan = {
            "days": [
                {
                    "skip_reason": None,
                    "resolved_project_for_top_suggestion": "Demo",
                    "top_sites": [{"domain": "demo.test"}],
                }
            ],
            "domain_project_counts": {},
        }
        with patch("core.cli_triage_domains.build_triage_plan_dict", return_value=plan), patch(
            "core.cli_triage_domains.questionary.checkbox"
        ) as checkbox_mock, patch("core.cli_triage_domains.questionary.confirm") as confirm_mock, patch(
            "core.cli_triage_domains.apply_triage_decisions_payload"
        ) as apply_mock:
            checkbox_mock.return_value.ask.return_value = ["demo.test"]
            confirm_mock.return_value.ask.return_value = True
            apply_mock.side_effect = [
                {"dry_run": True, "preview": "Planned config updates:", "would_apply": [], "skipped": 0, "errors": []},
                {"applied": 1, "skipped": 0, "preview": "Planned config updates:", "errors": []},
            ]
            result = self.runner.invoke(app, ["triage-domains", "--projects-config", cfg, "--today"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Domain triage apply complete", result.output)
        self.assertEqual(apply_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
