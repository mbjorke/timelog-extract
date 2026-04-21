"""Tests for the triage-apply command (core/cli_triage_apply.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.cli_triage_apply import _load_decisions, _validate_decision, _project_exists

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

    def test_apply_empty_decisions_list(self):
        """An empty decisions list should succeed with applied=0, skipped=0."""
        r = self._run_apply([])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["applied"], 0)
        self.assertEqual(out["skipped"], 0)
        self.assertEqual(out["errors"], [])

    def test_apply_missing_rule_value_field(self):
        """A decision missing rule_value should produce an error."""
        r = self._run_apply([{"project_name": "Demo", "rule_type": "match_terms"}])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertTrue(len(out["errors"]) > 0)
        self.assertIn("rule_value", out["errors"][0])

    def test_apply_missing_project_name_field(self):
        """A decision missing project_name should produce an error."""
        r = self._run_apply([{"rule_type": "match_terms", "rule_value": "x"}])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertTrue(len(out["errors"]) > 0)
        self.assertIn("project_name", out["errors"][0])

    def test_apply_dry_run_lists_would_apply(self):
        """Dry-run output contains would_apply list with correct fields."""
        r = self._run_apply(
            [{"day": "2026-04-15", "project_name": "Demo", "rule_type": "tracked_urls", "rule_value": "work.example.com"}],
            extra_args=["--dry-run"],
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out.get("dry_run"))
        self.assertEqual(len(out["would_apply"]), 1)
        entry = out["would_apply"][0]
        self.assertEqual(entry["project_name"], "Demo")
        self.assertEqual(entry["rule_type"], "tracked_urls")
        self.assertEqual(entry["rule_value"], "work.example.com")

    def test_apply_case_insensitive_project_match(self):
        """Project names are matched case-insensitively."""
        r = self._run_apply([{"day": "2026-04-15", "project_name": "DEMO", "rule_type": "match_terms", "rule_value": "casecheck"}])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["applied"], 1)

    def test_apply_invalid_json_input(self):
        """Passing a file with invalid JSON should exit with error JSON on stdout."""
        bad_file = Path(self.tmp) / "bad.json"
        bad_file.write_text("{not valid json}", encoding="utf-8")
        r = _run(["triage-apply", "--input", str(bad_file), "--projects-config", str(self.cfg)])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertIn("error", out)

    def test_apply_non_dict_json_input(self):
        """Passing a JSON array (not object) as top-level should produce an error."""
        arr_file = Path(self.tmp) / "array.json"
        arr_file.write_text(json.dumps([{"project_name": "Demo", "rule_type": "match_terms", "rule_value": "x"}]), encoding="utf-8")
        r = _run(["triage-apply", "--input", str(arr_file), "--projects-config", str(self.cfg)])
        self.assertNotEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertIn("error", out)


class TriageApplyHelpersTests(unittest.TestCase):
    """Unit tests for internal helper functions in cli_triage_apply."""

    def test_load_decisions_valid(self):
        """_load_decisions parses valid JSON from a file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"schema_version": 1, "decisions": [{"a": 1}]}, f)
            path = f.name
        try:
            decisions = _load_decisions(path)
            self.assertEqual(decisions, [{"a": 1}])
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_decisions_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ bad json }")
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _load_decisions(path)
            self.assertIn("Invalid JSON", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_decisions_non_dict_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([1, 2, 3], f)
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _load_decisions(path)
            self.assertIn("JSON object", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_decisions_missing_decisions_key_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"schema_version": 1}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _load_decisions(path)
            self.assertIn("decisions", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_decisions_decisions_not_list_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"decisions": {"key": "val"}}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _load_decisions(path)
            self.assertIn("array", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_validate_decision_valid(self):
        d = {"project_name": "MyProj", "rule_type": "match_terms", "rule_value": "foo"}
        name, rt, rv = _validate_decision(d, 0)
        self.assertEqual(name, "MyProj")
        self.assertEqual(rt, "match_terms")
        self.assertEqual(rv, "foo")

    def test_validate_decision_strips_whitespace(self):
        d = {"project_name": "  MyProj  ", "rule_type": "  tracked_urls  ", "rule_value": "  bar  "}
        name, rt, rv = _validate_decision(d, 0)
        self.assertEqual(name, "MyProj")
        self.assertEqual(rt, "tracked_urls")
        self.assertEqual(rv, "bar")

    def test_validate_decision_invalid_rule_type(self):
        d = {"project_name": "P", "rule_type": "invalid_type", "rule_value": "x"}
        with self.assertRaises(ValueError) as ctx:
            _validate_decision(d, 0)
        self.assertIn("rule_type", str(ctx.exception))

    def test_validate_decision_missing_project_name(self):
        d = {"rule_type": "match_terms", "rule_value": "x"}
        with self.assertRaises(ValueError) as ctx:
            _validate_decision(d, 2)
        self.assertIn("project_name", str(ctx.exception))
        self.assertIn("#2", str(ctx.exception))

    def test_validate_decision_missing_rule_value(self):
        d = {"project_name": "P", "rule_type": "match_terms"}
        with self.assertRaises(ValueError) as ctx:
            _validate_decision(d, 1)
        self.assertIn("rule_value", str(ctx.exception))

    def test_project_exists_returns_true_for_known(self):
        payload = {"projects": [{"name": "Demo"}, {"name": "Other"}]}
        self.assertTrue(_project_exists(payload, "Demo"))
        self.assertTrue(_project_exists(payload, "demo"))  # case-insensitive
        self.assertTrue(_project_exists(payload, "  Demo  "))  # strips whitespace

    def test_project_exists_returns_false_for_unknown(self):
        payload = {"projects": [{"name": "Demo"}]}
        self.assertFalse(_project_exists(payload, "Ghost"))

    def test_project_exists_empty_projects(self):
        payload = {"projects": []}
        self.assertFalse(_project_exists(payload, "Anything"))


if __name__ == "__main__":
    unittest.main()