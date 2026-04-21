"""Guardrails: tracked agent/Cursor docs must stay present (no silent deletion in refactors)."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Paths relative to repo root; keep in sync with AGENTS.md / triage agent workflow.
_REQUIRED_FILES = (
    "docs/runbooks/gittan-triage-agents.md",
    ".cursor/commands/gittan-triage-review.md",
    ".cursor/rules/gittan-triage-review.mdc",
)


class RepoAgentArtifactTests(unittest.TestCase):
    def test_required_agent_and_cursor_files_exist(self):
        missing = []
        empty = []
        for rel in _REQUIRED_FILES:
            path = REPO_ROOT / rel
            if not path.is_file():
                missing.append(rel)
                continue
            if path.stat().st_size < 50:
                empty.append(rel)
        self.assertEqual(
            missing,
            [],
            msg=f"Missing required files (restore or update tests if renamed): {missing}",
        )
        self.assertEqual(
            empty,
            [],
            msg=f"Required files unexpectedly tiny/empty: {empty}",
        )

    def test_gittan_triage_review_command_points_at_runbook(self):
        cmd = REPO_ROOT / ".cursor/commands/gittan-triage-review.md"
        text = cmd.read_text(encoding="utf-8")
        self.assertIn("docs/runbooks/gittan-triage-agents.md", text)


if __name__ == "__main__":
    unittest.main()
