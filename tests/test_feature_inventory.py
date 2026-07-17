"""Tests for the feature-inventory generator (Phase 1)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_feature_inventory.py"
_spec = importlib.util.spec_from_file_location("generate_feature_inventory", _SCRIPT)
fig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fig)


class DiscoveryTests(unittest.TestCase):
    def test_commands_include_known_commands_and_groups(self):
        rows = fig.discover_commands()
        names = {name for _group, name, _help in rows if name}
        groups = {group for group, name, _help in rows if not name}
        self.assertIn("jira-sync", names)
        self.assertIn("report", names)
        self.assertIn("reported", groups)  # the reported group
        # Group subcommands are attributed to their group.
        reported_subs = {name for group, name, _h in rows if group == "reported" and name}
        self.assertIn("sync", reported_subs)

    def test_command_help_is_first_doc_line(self):
        from core.cli_jira_sync import jira_sync as jira_sync_cmd

        expected = (jira_sync_cmd.__doc__ or "").strip().splitlines()[0].strip()
        rows = fig.discover_commands()
        help_by_name = {name: help_text for _g, name, help_text in rows if name}
        self.assertEqual(help_by_name["jira-sync"], expected)

    def test_collectors_include_known_sources(self):
        names = {name for name, _unit in fig.discover_collectors()}
        for source in ("Cursor", "Chrome", "Zed"):
            self.assertIn(source, names)

    def test_config_fields_include_integration_fields(self):
        fields = fig.discover_config_fields()
        for field in ("toggl_project_id", "jira_issue_key", "auto_report"):
            self.assertIn(field, fields)


class RenderTests(unittest.TestCase):
    def test_output_is_deterministic(self):
        self.assertEqual(fig.build_inventory(), fig.build_inventory())

    def test_output_has_banner_and_no_timestamp(self):
        out, _unspecced = fig.build_inventory()
        self.assertIn("do not edit by hand", out)
        self.assertNotIn("Generated:", out)  # no volatile date -> --check can diff

    def test_committed_inventory_is_up_to_date(self):
        # The generator must have been re-run after code changes (Phase 1 stale guard).
        content, _unspecced = fig.build_inventory()
        self.assertEqual(
            fig.OUTPUT_PATH.read_text(encoding="utf-8"),
            content,
            msg="Run: python scripts/generate_feature_inventory.py",
        )


class SpecLinkTests(unittest.TestCase):
    """Phase 2 traceability coupling (GH-230)."""

    def test_explicit_covers_wins_over_backtick_mention(self):
        # toggl-sync is backtick-mentioned in several planning docs, but the
        # toggl spec declares `covers: toggl-sync` — the explicit key must win.
        command_specs, _collectors, _unspecced = fig.build_feature_links()
        path, status = command_specs["toggl-sync"]
        self.assertEqual(path, "docs/task-prompts/toggl-posting-task.md")
        self.assertTrue(status)  # implementation_status is carried along

    def test_backtick_mention_links_a_spec(self):
        command_specs, _collectors, _unspecced = fig.build_feature_links()
        self.assertIn("jira-sync", command_specs)  # linked via backtick mention

    def test_unknown_feature_reports_no_spec(self):
        specs = fig.load_specs()
        linked = fig.link_feature_specs(["definitely-not-a-command"], specs)
        self.assertEqual(linked, {})

    def test_spec_cell_renders_no_spec_and_truncates_status(self):
        self.assertEqual(fig._spec_cell(None), "(no spec)")
        cell = fig._spec_cell(("docs/task-prompts/x-task.md", "s" * 100))
        self.assertIn("[x-task](../task-prompts/x-task.md)", cell)
        self.assertIn("…", cell)


class CheckModeTests(unittest.TestCase):
    def test_check_passes_when_current(self):
        self.assertEqual(fig.main(["--check"]), 0)

    def test_strict_fails_while_unspecced_surface_remains(self):
        # Advisory-by-default gate: --strict is the hard mode. This assertion
        # flips to 0 the day every command/collector has a linked spec.
        _cmd, _coll, unspecced = fig.build_feature_links()
        expected = 1 if unspecced else 0
        self.assertEqual(fig.main(["--check", "--strict"]), expected)


if __name__ == "__main__":
    unittest.main()
