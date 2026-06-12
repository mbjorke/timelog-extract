import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.repo_slug import resolve_path_repo_slug, slug_from_remote_url


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _make_repo(root: Path, remote: str) -> Path:
    repo = root / "project-alpha"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.test")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", remote)
    return repo


class SlugFromRemoteUrlTests(unittest.TestCase):
    def test_https_and_ssh_forms(self) -> None:
        self.assertEqual(
            slug_from_remote_url("https://github.com/Owner-A/Project-Alpha.git"),
            "owner-a/project-alpha",
        )
        self.assertEqual(
            slug_from_remote_url("git@github.com:owner-a/project-alpha.git"),
            "owner-a/project-alpha",
        )
        self.assertEqual(slug_from_remote_url(""), "")
        self.assertEqual(slug_from_remote_url(None), "")


class ResolvePathRepoSlugTests(unittest.TestCase):
    def test_repo_and_sibling_worktree_share_slug(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = _make_repo(root, "https://github.com/owner-a/project-alpha.git")
            _git(repo, "worktree", "add", "-q", str(root / "confident-hopper-fe58c2"))
            main_slug = resolve_path_repo_slug(str(repo))
            worktree_slug = resolve_path_repo_slug(str(root / "confident-hopper-fe58c2"))
            self.assertEqual(main_slug, "owner-a/project-alpha")
            self.assertEqual(worktree_slug, main_slug)

    def test_non_repo_dir_and_missing_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plain").mkdir()
            self.assertEqual(resolve_path_repo_slug(str(root / "plain")), "")
            # Deleted path nested under the project tree walks up to the repo.
            repo = _make_repo(root, "https://github.com/owner-a/project-alpha.git")
            gone = repo / ".claude" / "worktrees" / "gone-leaf-ab12cd"
            self.assertEqual(resolve_path_repo_slug(str(gone)), "owner-a/project-alpha")
        self.assertEqual(resolve_path_repo_slug(""), "")


if __name__ == "__main__":
    unittest.main()
