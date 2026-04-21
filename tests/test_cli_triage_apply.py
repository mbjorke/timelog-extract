"""Tests for the triage-apply command (core/cli_triage_apply.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = [sys.executable, str(REPO / "timelog_extract.py")]

_EXAMPLE_PROJECT = {
    "name": "Demo",
    "canonical_project": "Demo",
    "customer": "Demo",
    "match_terms": ["demo"],
    "tracked_urls": [],
    "aliases": ["Demo"],
    "tags": ["tech"],
    "ticket_mode": "optional",
    "default_client": "Demo",
    "email": "",
    "invoice_title": "",
    "invoice_description": "",
    "project_id": "Demo",
    "enabled": True,
}


def _write_config(tmp_dir: str, projects: list[dict]) -> Path:
    p = Path(tmp_dir) / "timelog_projects.json"
    p.write_text(json.dumps({"projects": projects}), encoding="utf-8")
    return p


def _decisions(decisions: list[dict]) -> str:
    return json.dumps({"schema_version": 1, "decisions": decisions})


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*CLI, *args],
        cwd=str(REPO),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TriageApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = _write_config(self.tmp, [dict(_EXAMPLE_PROJECT)])

    def _run_apply(self, decisions: list[dict], extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
        d_file = Path(self.tmp) / "decisions.json"
        d_file.write_text(_decisions(decisions), encoding="utf-8")
        args = ["triage-apply", "--input", str(d_file), "--projects-config", str(self.cfg)]
        if extra_args:
            args.extend(extra_args)
        return _run(args)

    def test_apply_writes_match_terms(self):
        r = self._run_apply([{"day": "2026-04-15", "project_name": "Demo", "rule_type": "match_terms", "rule_value": "newterm"}])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["applied"], 1)
        self.assertEqual(out["skipped"], 0)
        config = json.loads(self.cfg.read_text())
        terms = config["projects"][0]["match_terms"]
        self.assertIn("newterm", terms)

    def test_apply_writes_tracked_urls(self):
        r = self._run_apply([{"day": "2026-04-15", "project_name": "Demo", "rule_type": "tracked_urls", "rule_value": "app.demo.io"}])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        config = json.loads(self.cfg.read_text())
        urls = config["projects"][0]["tracked_urls"]
        self.assertIn("app.demo.io", urls)

    def test_apply_rejects_unknown_project(self):
        r = self._run_apply([{"day": "2026-04-15", "project_name": "Ghost", "rule_type": "match_terms", "rule_value": "foo"}])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertTrue(len(out["errors"]) > 0)
        self.assertIn("Ghost", out["errors"][0])

    def test_apply_allow_create_creates_project(self):
        r = self._run_apply(
            [{"day": "2026-04-15", "project_name": "NewProj", "rule_type": "match_terms", "rule_value": "newtool"}],
            extra_args=["--allow-create"],
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        config = json.loads(self.cfg.read_text())
        names = [p["name"] for p in config["projects"]]
        self.assertIn("NewProj", names)

    def test_apply_dry_run_does_not_write(self):
        before_mtime = os.path.getmtime(self.cfg)
        r = self._run_apply(
            [{"day": "2026-04-15", "project_name": "Demo", "rule_type": "match_terms", "rule_value": "dryterm"}],
            extra_args=["--dry-run"],
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out.get("dry_run"))
        self.assertEqual(os.path.getmtime(self.cfg), before_mtime)

    def test_apply_invalid_rule_type(self):
        r = self._run_apply([{"day": "2026-04-15", "project_name": "Demo", "rule_type": "bad_type", "rule_value": "x"}])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertTrue(len(out["errors"]) > 0)

    def test_apply_deduplicates_within_payload(self):
        decision = {"day": "2026-04-15", "project_name": "Demo", "rule_type": "match_terms", "rule_value": "dup"}
        r = self._run_apply([decision, decision])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["applied"], 1)
        self.assertEqual(out["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
