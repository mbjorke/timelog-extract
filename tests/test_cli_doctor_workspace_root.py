"""Tests for doctor workspace-root resolution in installed CLI contexts."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.workspace_root import runtime_workspace_root


class DoctorWorkspaceRootTests(unittest.TestCase):
    def test_returns_cwd_when_not_in_git_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            probe = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=tmpdir,
                check=False,
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                self.skipTest("Temp directory is inside a git repository")
            root = runtime_workspace_root(cwd=Path(tmpdir))
            self.assertEqual(root, Path(tmpdir).resolve())

    def test_prefers_git_toplevel_when_inside_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            nested = repo / "nested" / "dir"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True, text=True)
            root = runtime_workspace_root(cwd=nested)
            self.assertEqual(root, repo.resolve())


if __name__ == "__main__":
    unittest.main()
