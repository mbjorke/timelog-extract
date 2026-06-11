"""Tests for the status-surface anchor nudge and interactive mapping flow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.anchor_nudge import run_interactive_anchor_flow, status_anchor_line
from core.config import load_projects_config_payload, save_projects_config_payload


class StatusAnchorLineTests(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(status_anchor_line([]))

    def test_singular_and_listing(self):
        line = status_anchor_line([{"kind": "dir", "value": "timelog-extract", "hits": 280}])
        self.assertIn("1 unmapped activity anchor", line)
        self.assertIn("timelog-extract (working directory, 280)", line)

    def test_listing_includes_kind_label(self):
        line = status_anchor_line([{"kind": "branch", "value": "project-beta", "hits": 120}])
        self.assertIn("project-beta (git branch, 120)", line)

    def test_truncates_and_counts_remainder(self):
        anchors = [{"kind": "dir", "value": f"d{i}", "hits": 10 - i} for i in range(5)]
        line = status_anchor_line(anchors)
        self.assertIn("5 unmapped activity anchors", line)
        self.assertIn("+2 more", line)


class InteractiveAnchorFlowTests(unittest.TestCase):
    def _cfg(self, payload) -> Path:
        fd, path = tempfile.mkstemp(suffix=".json")
        import os

        os.close(fd)
        p = Path(path)
        self.addCleanup(p.unlink, missing_ok=True)
        save_projects_config_payload(p, payload)
        return p

    def _fake_select(self, answer):
        obj = MagicMock()
        obj.ask.return_value = answer
        return obj

    def test_maps_dir_to_existing_project(self):
        cfg = self._cfg({"projects": [{"name": "gittan", "match_terms": ["keep"], "tracked_urls": []}]})
        console = MagicMock()
        with patch("questionary.select", return_value=self._fake_select("gittan")):
            added = run_interactive_anchor_flow(
                console,
                [{"kind": "dir", "value": "timelog-extract", "hits": 280}],
                load_projects_config_payload(cfg)["projects"],
                str(cfg),
            )
        self.assertEqual(added, 1)
        data = load_projects_config_payload(cfg)
        terms = [str(t).lower() for t in data["projects"][0]["match_terms"]]
        self.assertIn("timelog-extract", terms)
        self.assertIn("keep", terms)

    def test_create_new_project_choice(self):
        cfg = self._cfg({"projects": []})
        console = MagicMock()
        with patch("questionary.select", return_value=self._fake_select("Create new project: newrepo")):
            added = run_interactive_anchor_flow(
                console, [{"kind": "dir", "value": "newrepo", "hits": 40}], [], str(cfg)
            )
        self.assertEqual(added, 1)
        data = load_projects_config_payload(cfg)
        names = [p["name"] for p in data["projects"]]
        self.assertIn("newrepo", names)

    def test_skip_leaves_config_unchanged(self):
        cfg = self._cfg({"projects": [{"name": "gittan", "match_terms": ["keep"], "tracked_urls": []}]})
        before = cfg.read_text(encoding="utf-8")
        console = MagicMock()
        with patch("questionary.select", return_value=self._fake_select("Skip")):
            added = run_interactive_anchor_flow(
                console,
                [{"kind": "dir", "value": "timelog-extract", "hits": 280}],
                [{"name": "gittan", "match_terms": ["keep"]}],
                str(cfg),
            )
        self.assertEqual(added, 0)
        self.assertEqual(cfg.read_text(encoding="utf-8"), before)

    def test_stop_halts_remaining_anchors(self):
        cfg = self._cfg({"projects": [{"name": "gittan", "match_terms": ["keep"], "tracked_urls": []}]})
        console = MagicMock()
        with patch("questionary.select", return_value=self._fake_select("Stop mapping")):
            added = run_interactive_anchor_flow(
                console,
                [{"kind": "dir", "value": "a", "hits": 50}, {"kind": "branch", "value": "b", "hits": 40}],
                [{"name": "gittan", "match_terms": ["keep"]}],
                str(cfg),
            )
        self.assertEqual(added, 0)


if __name__ == "__main__":
    unittest.main()
