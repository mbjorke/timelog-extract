"""Tests for core/live_terminal/mock_data.py - load_demo_mock_data()."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class LoadDemoMockDataTests(unittest.TestCase):
    """Tests for load_demo_mock_data() fixture loading."""

    def _reload_module(self):
        """Re-import the module to clear lru_cache between tests."""
        import importlib
        import core.live_terminal.mock_data as mod
        importlib.reload(mod)
        return mod

    def test_raises_file_not_found_when_fixture_missing(self):
        """Should raise FileNotFoundError when fixture path does not exist."""
        mod = self._reload_module()
        with TemporaryDirectory() as tmpdir:
            nonexistent = str(Path(tmpdir) / "does_not_exist.json")
            old = os.environ.get("GITTAN_DEMO_MOCK_DATA")
            try:
                os.environ["GITTAN_DEMO_MOCK_DATA"] = nonexistent
                mod = self._reload_module()
                with self.assertRaises(FileNotFoundError):
                    mod.load_demo_mock_data()
            finally:
                if old is None:
                    os.environ.pop("GITTAN_DEMO_MOCK_DATA", None)
                else:
                    os.environ["GITTAN_DEMO_MOCK_DATA"] = old

    def test_returns_dict_from_valid_fixture(self):
        """Should return a dict when the fixture JSON is valid."""
        sample_data = {"projects": ["A", "B"], "sessions": []}
        with TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "demo_mock_data.json"
            fixture_path.write_text(json.dumps(sample_data), encoding="utf-8")
            old = os.environ.get("GITTAN_DEMO_MOCK_DATA")
            try:
                os.environ["GITTAN_DEMO_MOCK_DATA"] = str(fixture_path)
                mod = self._reload_module()
                result = mod.load_demo_mock_data()
                self.assertIsInstance(result, dict)
                self.assertEqual(result["projects"], ["A", "B"])
            finally:
                if old is None:
                    os.environ.pop("GITTAN_DEMO_MOCK_DATA", None)
                else:
                    os.environ["GITTAN_DEMO_MOCK_DATA"] = old

    def test_env_var_override_used_when_set(self):
        """GITTAN_DEMO_MOCK_DATA env var points to a custom fixture path."""
        custom_data = {"custom_key": "custom_value"}
        with TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "custom_fixture.json"
            fixture_path.write_text(json.dumps(custom_data), encoding="utf-8")
            old = os.environ.get("GITTAN_DEMO_MOCK_DATA")
            try:
                os.environ["GITTAN_DEMO_MOCK_DATA"] = str(fixture_path)
                mod = self._reload_module()
                result = mod.load_demo_mock_data()
                self.assertEqual(result.get("custom_key"), "custom_value")
            finally:
                if old is None:
                    os.environ.pop("GITTAN_DEMO_MOCK_DATA", None)
                else:
                    os.environ["GITTAN_DEMO_MOCK_DATA"] = old

    def test_empty_env_var_uses_default_path(self):
        """Empty GITTAN_DEMO_MOCK_DATA falls back to the default fixture location."""
        old = os.environ.get("GITTAN_DEMO_MOCK_DATA")
        try:
            os.environ["GITTAN_DEMO_MOCK_DATA"] = ""
            mod = self._reload_module()
            # The default fixture may or may not exist in CI; verify no AttributeError.
            # If missing, FileNotFoundError is expected (not an import error).
            try:
                result = mod.load_demo_mock_data()
                self.assertIsInstance(result, dict)
            except FileNotFoundError:
                pass  # Acceptable: fixture absent in this environment
        finally:
            if old is None:
                os.environ.pop("GITTAN_DEMO_MOCK_DATA", None)
            else:
                os.environ["GITTAN_DEMO_MOCK_DATA"] = old

    def test_repo_root_resolves_correctly(self):
        """_repo_root() should return a valid directory (the project root)."""
        mod = self._reload_module()
        repo_root = mod._repo_root()
        self.assertTrue(repo_root.is_dir(), f"Expected directory, got: {repo_root}")
        # The repo root should contain at least 'core' or 'collectors' package directories.
        has_core = (repo_root / "core").is_dir()
        has_collectors = (repo_root / "collectors").is_dir()
        self.assertTrue(has_core or has_collectors, f"Unexpected repo root: {repo_root}")


if __name__ == "__main__":
    unittest.main()