"""Unit tests for core/live_terminal/mock_data.py."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LoadDemoMockDataTests(unittest.TestCase):
    """Tests for load_demo_mock_data fixture loader."""

    def _make_fixture(self, tmp_dir: str, content: dict) -> Path:
        path = Path(tmp_dir) / "demo_mock.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def _reload_module(self):
        """Import and return a fresh (uncached) version of the module."""
        import importlib
        import core.live_terminal.mock_data as mod
        # Clear the LRU cache so each test starts fresh.
        mod.load_demo_mock_data.cache_clear()
        return mod

    def test_env_override_loads_custom_fixture(self):
        """GITTAN_DEMO_MOCK_DATA env var overrides the default fixture path."""
        mod = self._reload_module()
        content = {"events": [{"source": "Cursor", "hours": 1.5}]}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._make_fixture(tmp, content)
            with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": str(fixture)}):
                mod.load_demo_mock_data.cache_clear()
                result = mod.load_demo_mock_data()
        self.assertEqual(result, content)

    def test_missing_fixture_raises_file_not_found(self):
        """FileNotFoundError is raised when no fixture exists at the resolved path."""
        mod = self._reload_module()
        nonexistent = "/tmp/__gittan_nonexistent_fixture_12345.json"
        with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": nonexistent}):
            mod.load_demo_mock_data.cache_clear()
            with self.assertRaises(FileNotFoundError):
                mod.load_demo_mock_data()

    def test_empty_env_override_uses_default_path_logic(self):
        """Empty GITTAN_DEMO_MOCK_DATA env var falls back to default path logic."""
        mod = self._reload_module()
        # When env var is empty, the function derives the default fixture path.
        # Rather than needing the real fixture to exist, patch the default path.
        content = {"sessions": []}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._make_fixture(tmp, content)
            # Override env to empty and patch _repo_root to point to tmp parent
            with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": ""}):
                mod.load_demo_mock_data.cache_clear()
                with patch.object(mod, "_repo_root", return_value=Path(tmp).parent):
                    # Default path: _repo_root() / "tests" / "fixtures" / "demo_mock_data.json"
                    # Create that path
                    default_fixture = Path(tmp).parent / "tests" / "fixtures" / "demo_mock_data.json"
                    default_fixture.parent.mkdir(parents=True, exist_ok=True)
                    default_fixture.write_text(json.dumps(content), encoding="utf-8")
                    mod.load_demo_mock_data.cache_clear()
                    result = mod.load_demo_mock_data()
        self.assertEqual(result, content)

    def test_result_is_dict(self):
        """Loaded fixture returns a dict."""
        mod = self._reload_module()
        content = {"key": "value"}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._make_fixture(tmp, content)
            with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": str(fixture)}):
                mod.load_demo_mock_data.cache_clear()
                result = mod.load_demo_mock_data()
        self.assertIsInstance(result, dict)

    def test_lru_cache_returns_same_object(self):
        """Cached calls return the exact same object reference."""
        mod = self._reload_module()
        content = {"cached": True}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._make_fixture(tmp, content)
            with patch.dict(os.environ, {"GITTAN_DEMO_MOCK_DATA": str(fixture)}):
                mod.load_demo_mock_data.cache_clear()
                first = mod.load_demo_mock_data()
                second = mod.load_demo_mock_data()
        self.assertIs(first, second)

    def tearDown(self):
        # Always clear the cache after each test to avoid pollution.
        import core.live_terminal.mock_data as mod
        mod.load_demo_mock_data.cache_clear()


if __name__ == "__main__":
    unittest.main()