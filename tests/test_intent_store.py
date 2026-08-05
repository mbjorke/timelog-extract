"""A session bound by decision beats whatever the text matched.

A chat carries no repo and no working directory, so nothing observable says whose
work it was. The alternative to a `match_term` — a rule that then matches every
future event containing that text — is a binding on the session itself. These
tests cover the store, the override, the queue that gets asked, and the property
that matters end to end: a bound session shows up attributed in a real report.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from core.intent_store import (
    apply_intents,
    intent_path,
    read_intents,
    record_intent,
    resolve_intents,
    unbound_sessions,
)

UNCAT = "Uncategorized"


def event(session: str | None, project: str, hour: int = 9, label: str = "") -> dict:
    ev = {
        "source": "Claude Desktop (Code)",
        "timestamp": datetime(2026, 7, 25, hour, 0, tzinfo=timezone.utc),
        "detail": "3 turns",
        "project": project,
    }
    if session:
        anchors: dict = {"session": session}
        if label:
            anchors["label"] = label
        ev["anchors"] = anchors
    return ev


class RecordIntentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "intent.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_is_appended_not_rewritten(self):
        record_intent("s1", "Alpha", path=self.path)
        record_intent("s1", "Beta", path=self.path)
        self.assertEqual(len(read_intents(path=self.path)), 2, "history must be preserved")

    def test_latest_record_wins(self):
        record_intent("s1", "Alpha", path=self.path)
        record_intent("s1", "Beta", path=self.path)
        bindings = resolve_intents(path=self.path)
        self.assertEqual(bindings[("session", "s1")]["project"], "Beta")

    def test_record_carries_provenance(self):
        record = record_intent("s1", "Alpha", via="intent-prompt", note="phone chat", path=self.path)
        self.assertEqual(record["key_kind"], "session")
        self.assertEqual(record["via"], "intent-prompt")
        self.assertEqual(record["note"], "phone chat")
        self.assertEqual(record["schema_version"], 1)

    def test_blank_key_or_project_is_rejected(self):
        with self.assertRaises(ValueError):
            record_intent("  ", "Alpha", path=self.path)
        with self.assertRaises(ValueError):
            record_intent("s1", "   ", path=self.path)

    def test_unknown_key_kind_names_the_known_ones(self):
        with self.assertRaises(ValueError) as ctx:
            record_intent("s1", "Alpha", key_kind="telepathy", path=self.path)
        self.assertIn("session", str(ctx.exception))

    def test_garbage_lines_are_skipped_not_fatal(self):
        record_intent("s1", "Alpha", path=self.path)
        self.path.write_text(self.path.read_text(encoding="utf-8") + "not json\n\n", encoding="utf-8")
        self.assertEqual(len(read_intents(path=self.path)), 1)

    def test_missing_log_reads_as_empty(self):
        self.assertEqual(read_intents(path=Path(self._tmp.name) / "nope.jsonl"), [])

    def test_default_path_lives_in_the_data_dir(self):
        self.assertEqual(
            intent_path(Path("/home/op")), Path("/home/op/.gittan/intent-capture.jsonl")
        )


class ApplyIntentsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "intent.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_bound_session_is_reprojected(self):
        record_intent("s1", "project-alpha", path=self.path)
        events, changed = apply_intents([event("s1", UNCAT)], path=self.path)
        self.assertEqual(changed, 1)
        self.assertEqual(events[0]["project"], "project-alpha")

    def test_the_original_event_is_not_mutated(self):
        record_intent("s1", "project-alpha", path=self.path)
        original = event("s1", UNCAT)
        apply_intents([original], path=self.path)
        self.assertEqual(original["project"], UNCAT)

    def test_reprojection_records_where_the_project_came_from(self):
        """"Why is this project-alpha?" must be answerable from the row itself."""
        record_intent("s1", "project-alpha", path=self.path)
        events, _ = apply_intents([event("s1", UNCAT)], path=self.path)
        anchors = events[0]["anchors"]
        self.assertEqual(anchors["project_from"], "intent")
        self.assertEqual(anchors["project_before_intent"], UNCAT)
        self.assertEqual(anchors["session"], "s1", "existing anchors survive")

    def test_intent_overrides_a_text_match(self):
        """Confirmed contract (maintainer, 2026-07-26): the decision beats the pattern.

        Without this, a stale match_term could silently override an explicit
        answer and asking the question would be pointless.
        """
        record_intent("s1", "project-alpha", path=self.path)
        events, changed = apply_intents([event("s1", "MatchedByTerm")], path=self.path)
        self.assertEqual(changed, 1)
        self.assertEqual(events[0]["project"], "project-alpha")
        self.assertEqual(events[0]["anchors"]["project_before_intent"], "MatchedByTerm")

    def test_already_correct_event_is_left_alone(self):
        record_intent("s1", "project-alpha", path=self.path)
        events, changed = apply_intents([event("s1", "project-alpha")], path=self.path)
        self.assertEqual(changed, 0)
        self.assertNotIn("project_from", events[0].get("anchors", {}))

    def test_events_without_a_session_anchor_are_untouched(self):
        record_intent("s1", "project-alpha", path=self.path)
        events, changed = apply_intents([event(None, UNCAT)], path=self.path)
        self.assertEqual(changed, 0)
        self.assertEqual(events[0]["project"], UNCAT)

    def test_no_bindings_is_a_cheap_no_op(self):
        events, changed = apply_intents([event("s1", UNCAT)], path=self.path)
        self.assertEqual(changed, 0)
        self.assertEqual(events[0]["project"], UNCAT)


class UnboundSessionsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "intent.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_unattributed_sessions_are_asked_about(self):
        rows = unbound_sessions(
            [event("s1", UNCAT), event("s2", "Alpha")], path=self.path
        )
        self.assertEqual([row["session"] for row in rows], ["s1"])

    def test_already_bound_sessions_drop_out_of_the_queue(self):
        record_intent("s1", "project-alpha", path=self.path)
        rows = unbound_sessions([event("s1", UNCAT), event("s2", UNCAT)], path=self.path)
        self.assertEqual([row["session"] for row in rows], ["s2"])

    def test_one_row_per_session_with_a_count(self):
        rows = unbound_sessions(
            [event("s1", UNCAT, 9), event("s1", UNCAT, 10), event("s1", UNCAT, 11)],
            path=self.path,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["events"], 3)
        self.assertEqual(rows[0]["first_seen"].hour, 9)
        self.assertEqual(rows[0]["last_seen"].hour, 11)

    def test_newest_session_is_asked_about_first(self):
        rows = unbound_sessions(
            [event("old", UNCAT, 9), event("new", UNCAT, 16)], path=self.path
        )
        self.assertEqual([row["session"] for row in rows], ["new", "old"])

    def test_label_is_carried_so_the_question_is_answerable(self):
        rows = unbound_sessions([event("s1", UNCAT, label="Fix the widget")], path=self.path)
        self.assertEqual(rows[0]["label"], "Fix the widget")

    def test_sessionless_events_are_not_askable(self):
        self.assertEqual(unbound_sessions([event(None, UNCAT)], path=self.path), [])


class ReportAttributionTests(unittest.TestCase):
    """End to end: bind a session, and the hours move in a real report."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".gittan").mkdir(parents=True)
        self.config = self.home / "projects.json"
        self.config.write_text(
            json.dumps(
                {
                    "projects": [{"name": "project-alpha", "match_terms": ["project-alpha-term"]}],
                    "worklog": "none.md",
                }
            ),
            encoding="utf-8",
        )
        # A desktop-code session with no git metadata: hours, no anchor, so the
        # report can only call it Uncategorized until a decision binds it.
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_capture_desktop_code import write_desktop_code_cache

        write_desktop_code_cache(self.home, repo_slug=None)

    def tearDown(self):
        self._tmp.cleanup()

    def _hours_by_project(self) -> dict:
        from core.report_service import run_timelog_report

        with patch("core.report_service.HOME", self.home):
            report = run_timelog_report(
                str(self.config),
                "2026-07-25",
                "2026-07-25",
                {
                    "quiet": True,
                    "screen_time": "off",
                    "chrome_source": "off",
                    "mail_source": "off",
                    "github_source": "off",
                    "include_uncategorized": True,
                },
            )
        return {
            project: sum(block["hours"] for block in days.values())
            for project, days in report.project_reports.items()
        }

    def test_unbound_session_is_uncategorized(self):
        hours = self._hours_by_project()
        self.assertIn(UNCAT, hours, f"expected unattributed hours, got {hours}")
        self.assertGreater(hours[UNCAT], 0)

    def test_binding_the_session_moves_the_hours(self):
        before = self._hours_by_project()
        unattributed = before[UNCAT]

        record_intent("session_01DESKTOP", "project-alpha", via="intent-prompt", home=self.home)

        after = self._hours_by_project()
        self.assertAlmostEqual(after.get("project-alpha", 0), unattributed, places=4)
        self.assertNotIn(UNCAT, after, f"nothing should be left unattributed: {after}")


class UnknownProjectIsRejectedTests(unittest.TestCase):
    """A typo must not become an authoritative binding (Greptile P1 on #469).

    `docs/specs/intent-capture.md` already required this — *"the record is
    rejected with a clear error / nothing is appended to the log"* — and the
    implementation only printed a note. The consequence is not cosmetic: because
    a binding outranks a `match_term`, a mistyped name moves the hours to a
    project that does not exist *and* off `Uncategorized`, so they stop showing
    up in triage and surface later as a phantom bucket on an invoice.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        (self.home / ".gittan").mkdir()
        self.config = self.home / "projects.json"
        self.config.write_text(
            json.dumps(
                {
                    "projects": [{"name": "project-alpha", "match_terms": ["project-alpha-term"]}],
                    "worklog": "none.md",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        from typer.testing import CliRunner

        from core.cli import app

        with patch("pathlib.Path.home", return_value=self.home):
            return CliRunner().invoke(
                app, ["intent", "--projects-config", str(self.config), *args]
            )

    def test_typo_in_set_is_refused_and_nothing_is_written(self):
        result = self._run("--set", "s1=Custmer X")
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(read_intents(home=self.home), [], "a refused binding must not append")

    def test_the_error_names_the_projects_that_do_exist(self):
        result = self._run("--set", "s1=Ghost Project")
        self.assertIn("project-alpha", result.output)

    def test_a_configured_project_still_binds(self):
        result = self._run("--set", "s1=project-alpha")
        self.assertEqual(result.exit_code, 0, result.output)
        bindings = resolve_intents(home=self.home)
        self.assertEqual(bindings[("session", "s1")]["project"], "project-alpha")

    def test_failed_batch_writes_nothing(self):
        """A later typo must not leave earlier --set bindings recorded."""
        result = self._run("--set", "s1=project-alpha", "--set", "s2=Ghost Project")
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Ghost Project", result.output)
        self.assertEqual(read_intents(home=self.home), [])

    def test_empty_project_list_refuses_any_set(self):
        """No named profiles must not make every project name look valid."""
        self.config.write_text(json.dumps({"projects": [], "worklog": "none.md"}), encoding="utf-8")
        result = self._run("--set", "s1=Anything")
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("no configured projects", result.output.lower())
        self.assertEqual(read_intents(home=self.home), [])


class LocalTimeDisplayTests(unittest.TestCase):
    """Stored stamps are UTC; a human reading them must see their own clock.

    Caught by the maintainer: 10:10 UTC is 13:10 on an EEST wall clock. For a
    question whose purpose is recognising a session, the wrong clock makes it
    unanswerable.
    """

    def test_utc_stamp_renders_in_the_readers_zone(self):
        from core.cli_evidence import _local_stamp

        with patch.dict(os.environ, {"TZ": "Europe/Mariehamn"}):
            time.tzset()
            try:
                rendered = _local_stamp("2026-07-26T10:10:00+00:00")
            finally:
                time.tzset()
        self.assertIn("13:10", rendered, f"expected an EEST wall clock, got {rendered}")
        self.assertNotIn("10:10", rendered)

    def test_blank_stamp_reads_as_a_dash(self):
        from core.cli_evidence import _local_stamp

        self.assertEqual(_local_stamp(None), "—")
        self.assertEqual(_local_stamp("   "), "—")

    def test_unparseable_stamp_is_shown_not_swallowed(self):
        from core.cli_evidence import _local_stamp

        self.assertEqual(_local_stamp("not a timestamp"), "not a timestamp")


class InteractiveIntentCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        (self.home / ".gittan").mkdir()
        self.config = self.home / "projects.json"
        self.config.write_text(
            json.dumps(
                {
                    "projects": [{"name": "project-alpha", "match_terms": ["project-alpha-term"]}],
                    "worklog": "none.md",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        from typer.testing import CliRunner

        from core.cli import app

        with patch("pathlib.Path.home", return_value=self.home):
            return CliRunner().invoke(
                app, ["intent", "--projects-config", str(self.config), *args]
            )

    def test_interactive_mode_fails_if_no_tty(self):
        with patch("core.intent_store.unbound_sessions", return_value=[{"session": "s1", "first_seen": "2026-07-26T10:10:00+00:00", "label": "test", "source": "chrome", "events": 1}]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=False):
            result = self._run()
            self.assertEqual(result.exit_code, 1)
            self.assertIn("requires an interactive terminal", result.output)

    def test_interactive_mode_empty_state_if_no_unbound_sessions(self):
        with patch("core.intent_store.unbound_sessions", return_value=[]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True):
            result = self._run()
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No unattributed sessions in this window", result.output)

    def test_interactive_mode_can_bind_session(self):
        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        fake_select_mock.ask.return_value = "project-alpha"

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock):
            result = self._run()
            self.assertEqual(result.exit_code, 0)
            self.assertIn("bound → project-alpha", result.output)
            bindings = resolve_intents(home=self.home)
            self.assertEqual(bindings[("session", "s1")]["project"], "project-alpha")

    def test_interactive_mode_can_skip_session(self):
        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        from core.cli_intent import SKIP_SESSION
        fake_select_mock.ask.return_value = SKIP_SESSION

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock):
            result = self._run()
            self.assertEqual(result.exit_code, 0)
            self.assertIn("skipped", result.output)
            bindings = resolve_intents(home=self.home)
            self.assertNotIn(("session", "s1"), bindings)

    def test_interactive_mode_can_cancel_mapping(self):
        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        from core.cli_intent import CANCEL_MAPPING
        fake_select_mock.ask.return_value = CANCEL_MAPPING

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock):
            result = self._run()
            self.assertEqual(result.exit_code, 130)
            self.assertIn("Session mapping cancelled", result.output)
            bindings = resolve_intents(home=self.home)
            self.assertNotIn(("session", "s1"), bindings)

    def test_project_named_cancel_is_bound_not_treated_as_cancel(self):
        """A configured project may legitimately be called "Cancel".

        The menu mixes project names with control labels. Comparing the answer
        as a string made picking such a project abort the run and leave the
        session unattributed — the opposite of what the user asked for.
        """
        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        fake_select_mock.ask.return_value = "Cancel"  # the project, not the action

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock):
            result = self._run()
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("bound → Cancel", result.output)
            bindings = resolve_intents(home=self.home)
            self.assertEqual(bindings[("session", "s1")]["project"], "Cancel")

    def test_project_named_skip_this_session_is_bound_not_skipped(self):
        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        fake_select_mock.ask.return_value = "Skip this session"

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock):
            result = self._run()
            self.assertEqual(result.exit_code, 0, msg=result.output)
            bindings = resolve_intents(home=self.home)
            self.assertEqual(bindings[("session", "s1")]["project"], "Skip this session")

    def test_control_choices_carry_sentinel_values_not_labels(self):
        """The menu must offer control actions by identity, not by string."""
        from core.cli_intent import CANCEL_MAPPING, SKIP_SESSION

        fake_session = {
            "session": "s1",
            "first_seen": "2026-07-26T10:10:00+00:00",
            "label": "My Chat",
            "source": "slack",
            "events": 3,
        }
        fake_select_mock = mock.Mock()
        fake_select_mock.ask.return_value = CANCEL_MAPPING

        with patch("core.intent_store.unbound_sessions", return_value=[fake_session]), \
             patch("core.session_capture.collect_device_events", return_value=[]), \
             patch("core.anchor_nudge.should_prompt", return_value=True), \
             patch("questionary.select", return_value=fake_select_mock) as select_mock:
            self._run()

        values = [c.value for c in select_mock.call_args.kwargs["choices"]]
        self.assertIs(values[-1], CANCEL_MAPPING)
        self.assertIs(values[-2], SKIP_SESSION)
        self.assertNotIn("Cancel", values, "a bare string would collide with a project name")

    def test_non_interactive_run_collects_nothing(self):
        """The terminal gate must precede the expensive scan, not follow it."""
        with patch("core.session_capture.collect_device_events") as collect_mock, \
             patch("core.anchor_nudge.should_prompt", return_value=False):
            result = self._run()
            self.assertEqual(result.exit_code, 1)
            self.assertIn("requires an interactive terminal", result.output)
            collect_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
