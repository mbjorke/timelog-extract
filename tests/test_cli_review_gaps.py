"""Tests for report-gap attribution UX (`gittan review --gaps`, GH-234)."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core.cli_review_gaps import run_gap_attribution_review
from core.config import load_projects_config_payload, save_projects_config_payload


def _prof(name: str, terms: list[str], customer: str | None = None):
    return {
        "name": name,
        "match_terms": sorted({t.lower() for t in terms + [name] if t}),
        "tracked_urls": [],
        "enabled": True,
        "email": "",
        "customer": customer or name,
        "invoice_title": "",
        "invoice_description": "",
    }


def _fake_report(profiles: list[dict], events: list[dict]):
    args = argparse.Namespace(gap_minutes=15, min_session=15, min_session_passive=5, exclude="")
    return mock.Mock(
        profiles=profiles,
        included_events=events,
        args=args,
    )


def _event(detail: str, source: str = "Cursor"):
    return {
        "source": source,
        "detail": detail,
        "project": "Uncategorized",
        "timestamp": datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    }


class GapAttributionJsonModeTests(unittest.TestCase):
    """Read-only --json mode never writes config and reports candidate previews."""

    def test_json_out_lists_existing_projects_only_no_write(self):
        profiles = [_prof("Acme", ["acme"], customer="Acme Inc")]
        events = [_event("Worked on acme-feature implementation") for _ in range(3)]
        fake_report = _fake_report(profiles, events)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": profiles})
            before = cfg.read_text(encoding="utf-8")

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report):
                with mock.patch("builtins.print") as print_mock:
                    has_candidates = run_gap_attribution_review(
                        today=True,
                        projects_config=str(cfg),
                        json_out=True,
                    )

            # Config file is untouched — read-only surface.
            self.assertEqual(cfg.read_text(encoding="utf-8"), before)
            self.assertTrue(has_candidates)
            printed = print_mock.call_args[0][0]
            payload = json.loads(printed)
            self.assertEqual(payload["existing_projects"], ["Acme"])
            self.assertGreaterEqual(len(payload["gaps"]), 1)
            gap = payload["gaps"][0]
            self.assertIn("Acme", gap["candidate_projects"])
            self.assertEqual(gap["candidate_projects"]["Acme"]["customer"], "Acme Inc")
            self.assertGreater(gap["candidate_projects"]["Acme"]["matched_hours"], 0)

    def test_json_out_empty_when_no_uncategorized_events(self):
        profiles = [_prof("Acme", ["acme"])]
        fake_report = _fake_report(profiles, [])

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": profiles})

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report):
                with mock.patch("builtins.print") as print_mock:
                    has_candidates = run_gap_attribution_review(
                        today=True,
                        projects_config=str(cfg),
                        json_out=True,
                    )

            self.assertFalse(has_candidates)
            payload = json.loads(print_mock.call_args[0][0])
            self.assertEqual(payload["gaps"], [])


class GapAttributionInteractiveTests(unittest.TestCase):
    """Interactive flow: existing-line-only guard, preview-before-write, backup."""

    def test_apply_to_existing_project_writes_with_backup(self):
        profiles = [_prof("Acme", ["acme"], customer="Acme Inc")]
        events = [_event("Worked on acme-feature implementation") for _ in range(3)]
        fake_report = _fake_report(profiles, events)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": profiles})

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report), mock.patch(
                "core.cli_review_gaps.questionary.select"
            ) as select_mock, mock.patch("core.cli_review_gaps.questionary.confirm") as confirm_mock, mock.patch(
                "core.cli_review_gaps.backup_projects_config_if_exists"
            ) as backup_mock:
                select_mock.return_value.ask.return_value = "Acme"
                confirm_mock.return_value.ask.return_value = True
                backup_mock.return_value = cfg.parent / "backup.json"

                run_gap_attribution_review(
                    today=True,
                    projects_config=str(cfg),
                    json_out=False,
                )

            backup_mock.assert_called_once_with(cfg)
            saved = load_projects_config_payload(cfg)
            acme = next(p for p in saved["projects"] if p["name"] == "Acme")
            self.assertIn("acme-feature", acme["match_terms"])

    def test_never_offers_create_new_project_choice(self):
        """Guard (GH-234): the select prompt only ever contains existing project
        names plus skip/quit — never a "create new project" option."""
        profiles = [_prof("Acme", ["acme"])]
        events = [_event("Worked on acme-feature implementation") for _ in range(3)]
        fake_report = _fake_report(profiles, events)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": profiles})

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report), mock.patch(
                "core.cli_review_gaps.questionary.select"
            ) as select_mock, mock.patch("core.cli_review_gaps.questionary.confirm") as confirm_mock:
                select_mock.return_value.ask.return_value = "Stop reviewing gaps"
                confirm_mock.return_value.ask.return_value = False

                run_gap_attribution_review(
                    today=True,
                    projects_config=str(cfg),
                    json_out=False,
                )

            choices = select_mock.call_args.kwargs.get("choices") or select_mock.call_args[0][1]
            for choice in choices:
                self.assertNotIn("Create new project", str(choice))
            self.assertIn("Acme", choices)

    def test_refuses_write_if_target_project_no_longer_exists(self):
        """Defense-in-depth: if the config no longer has the selected project by
        apply time (e.g. concurrent edit), refuse rather than create a new
        slug-only profile."""
        profiles = [_prof("Acme", ["acme"])]
        events = [_event("Worked on acme-feature implementation") for _ in range(3)]
        fake_report = _fake_report(profiles, events)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": profiles})

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report), mock.patch(
                "core.cli_review_gaps.questionary.select"
            ) as select_mock, mock.patch("core.cli_review_gaps.questionary.confirm") as confirm_mock, mock.patch(
                "core.cli_review_gaps.save_projects_config_payload"
            ) as save_mock:
                select_mock.return_value.ask.return_value = "Acme"
                confirm_mock.return_value.ask.return_value = True
                # Simulate concurrent edit: config on disk no longer has "Acme".
                save_projects_config_payload(cfg, {"projects": []})

                run_gap_attribution_review(
                    today=True,
                    projects_config=str(cfg),
                    json_out=False,
                )

            save_mock.assert_not_called()

    def test_no_existing_projects_skips_without_writing(self):
        events = [_event("Worked on acme-feature implementation") for _ in range(3)]
        fake_report = _fake_report([], events)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            save_projects_config_payload(cfg, {"projects": []})
            before = cfg.read_text(encoding="utf-8")

            with mock.patch("core.report_service.run_timelog_report", return_value=fake_report):
                has_candidates = run_gap_attribution_review(
                    today=True,
                    projects_config=str(cfg),
                    json_out=False,
                )

            self.assertFalse(has_candidates)
            self.assertEqual(cfg.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
