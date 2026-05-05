from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import load_projects_config_payload, save_projects_config_payload
from core.inline_mapping_apply import run_inline_mapping_apply_loop


class InlineMappingApplyTests(unittest.TestCase):
    def test_prompt_noop_keeps_config_unchanged(self) -> None:
        config_path = self._write_config(
            {
                "projects": [
                    {"name": "Project Alpha", "match_terms": ["alpha-token", "stale-term"], "tracked_urls": []},
                    {"name": "Project Beta", "match_terms": ["beta-token"], "tracked_urls": []},
                ]
            }
        )
        self.addCleanup(config_path.unlink, missing_ok=True)
        before = load_projects_config_payload(config_path)
        with patch(
            "core.inline_mapping_apply.build_inline_mapping_candidates",
            return_value=[
                {"kind": "host", "host": "new.example.dev", "hits": 4},
                {
                    "kind": "stale_term",
                    "project_name": "Project Alpha",
                    "rule_type": "match_terms",
                    "rule_value": "stale-term",
                },
            ],
        ), patch("core.inline_mapping_apply.typer.confirm", side_effect=[False, False]):
            run_inline_mapping_apply_loop(
                events=[],
                profiles=before["projects"],
                projects_config=str(config_path),
                interactive=True,
            )
        after = load_projects_config_payload(config_path)
        self.assertEqual(before, after)

    def test_yes_path_applies_host_and_moves_stale_term(self) -> None:
        config_path = self._write_config(
            {
                "projects": [
                    {"name": "Project Alpha", "match_terms": ["alpha-token", "stale-term"], "tracked_urls": []},
                    {"name": "Project Beta", "match_terms": ["beta-token"], "tracked_urls": []},
                    {"name": "Project Gamma", "match_terms": ["gamma-token"], "tracked_urls": []},
                ]
            }
        )
        self.addCleanup(config_path.unlink, missing_ok=True)
        with patch(
            "core.inline_mapping_apply.build_inline_mapping_candidates",
            return_value=[
                {"kind": "host", "host": "new.example.dev", "hits": 4},
                {
                    "kind": "stale_term",
                    "project_name": "Project Alpha",
                    "rule_type": "match_terms",
                    "rule_value": "stale-term",
                },
            ],
        ), patch("core.inline_mapping_apply.typer.confirm", side_effect=[True, True, True]), patch(
            "core.inline_mapping_apply.typer.prompt", side_effect=["2", "1"]
        ):
            run_inline_mapping_apply_loop(
                events=[],
                profiles=load_projects_config_payload(config_path)["projects"],
                projects_config=str(config_path),
                interactive=True,
            )

        after = load_projects_config_payload(config_path)
        projects = {row["name"]: row for row in after["projects"]}
        self.assertIn("new.example.dev", projects["Project Beta"]["tracked_urls"])
        self.assertNotIn("stale-term", projects["Project Alpha"]["match_terms"])
        self.assertIn("stale-term", projects["Project Beta"]["match_terms"])

    def _write_config(self, payload: dict) -> Path:
        fd, path = tempfile.mkstemp(suffix=".json")
        Path(path).unlink(missing_ok=True)
        config_path = Path(path)
        save_projects_config_payload(config_path, payload)
        return config_path


if __name__ == "__main__":
    unittest.main()
