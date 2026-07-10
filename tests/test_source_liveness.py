"""Tests for the silent-source watchdog (GH-366).

Fixture replays of the #345/#363 incident shapes with neutral data: a source
that was recently active produces zero events while sibling sources stay busy.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from core.source_liveness import (
    SilentSourceFinding,
    apply_liveness_to_collector_status,
    detect_silent_sources,
    events_by_source_day,
    shadow_baseline_by_source,
    silent_source_warning_lines,
)

UTC = timezone.utc


def _event(source: str, day: str, hour: int = 10) -> dict:
    y, m, d = (int(part) for part in day.split("-"))
    return {
        "source": source,
        "timestamp": datetime(y, m, d, hour, 0, tzinfo=UTC),
        "detail": "work on project-alpha",
        "project": "project-alpha",
    }


def _write_shadow_records(home: Path, records: list[dict]) -> None:
    events_dir = home / ".gittan" / "evidence" / "events"
    events_dir.mkdir(parents=True)
    by_month: dict[str, list[dict]] = {}
    for rec in records:
        by_month.setdefault(rec["observed_at"][:7], []).append(rec)
    for month, recs in by_month.items():
        path = events_dir / f"{month}.jsonl"
        path.write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs), encoding="utf-8"
        )


def _shadow_record(source: str, day: str) -> dict:
    return {"observed_at": f"{day}T10:00:00+00:00", "source": source}


class ShadowBaselineTests(unittest.TestCase):
    def test_counts_days_and_events_in_lookback_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-07"),
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-10"),  # window day: out
                    _shadow_record("Chrome", "2026-02-01"),  # too old: out
                ],
            )
            baseline = shadow_baseline_by_source(date(2026, 3, 10), home=home)
        self.assertEqual(
            baseline,
            {
                "Cursor (agent)": {
                    "days_active": 2,
                    "last_active": "2026-03-08",
                    "events": 3,
                }
            },
        )

    def test_missing_store_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                shadow_baseline_by_source(date(2026, 3, 10), home=Path(tmp)), {}
            )


class DetectSilentSourcesTests(unittest.TestCase):
    """Replays of the #345 / #363 shape: active history, silent window, busy siblings."""

    def _detect(self, events, home, collector_status=None):
        return detect_silent_sources(
            events,
            collector_status if collector_status is not None else {},
            datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
            home=home,
        )

    def test_flatlined_source_with_active_siblings_alarms(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-09"),
                ],
            )
            events = [_event("Cursor", "2026-03-10"), _event("Chrome", "2026-03-10")]
            findings = self._detect(events, home)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.source, "Cursor (agent)")
        self.assertEqual(finding.baseline, "shadow-log")
        self.assertEqual(finding.scope, "window")
        self.assertEqual(finding.last_active, "2026-03-09")

    def test_idle_window_never_alarms(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-09"),
                ],
            )
            self.assertEqual(self._detect([], home), [])

    def test_active_source_does_not_alarm(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-09"),
                ],
            )
            events = [_event("Cursor (agent)", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])

    def test_disabled_source_never_alarms(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Claude Desktop (Code)", "2026-03-08"),
                    _shadow_record("Claude Desktop (Code)", "2026-03-09"),
                ],
            )
            events = [_event("Claude Desktop", "2026-03-10")]
            status = {
                "Claude Desktop (Code)": {"enabled": False, "reason": "off", "events": 0}
            }
            self.assertEqual(self._detect(events, home, status), [])

    def test_derived_source_skipped_when_parent_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-08"),
                    _shadow_record("Cursor (agent)", "2026-03-09"),
                ],
            )
            # A family sibling is active, but the parent collector is disabled.
            events = [_event("Cursor checkpoints", "2026-03-10")]
            status = {"Cursor": {"enabled": False, "reason": "off", "events": 0}}
            self.assertEqual(self._detect(events, home, status), [])

    def test_no_family_sibling_active_is_doctor_info_not_report_alarm(self):
        # Windsurf was active recently but has no sibling log stream: silence
        # just means the app was not used today — no report warning.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Windsurf", "2026-03-08"),
                    _shadow_record("Windsurf", "2026-03-09"),
                ],
            )
            events = [_event("Cursor", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])

    def test_content_derived_sources_never_alarm(self):
        # WordPress events are parsed out of Chrome history; zero means "no
        # matching URLs", not a broken stream.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("WordPress", "2026-03-08"),
                    _shadow_record("WordPress", "2026-03-09"),
                ],
            )
            events = [_event("Chrome", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])

    def test_long_quiet_source_is_not_an_alarm(self):
        # Last activity 6 days before the window — outside MAX_SILENT_GAP_DAYS,
        # so this is "not in use lately", not a fresh flatline.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-03"),
                    _shadow_record("Cursor (agent)", "2026-03-04"),
                ],
            )
            events = [_event("Cursor", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])

    def test_single_baseline_day_is_not_enough(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(home, [_shadow_record("Cursor (agent)", "2026-03-09")])
            events = [_event("Cursor", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])

    def test_comparator_sources_never_alarm(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Timely Memory", "2026-03-08"),
                    _shadow_record("Timely Memory", "2026-03-09"),
                ],
            )
            events = [_event("Cursor", "2026-03-10")]
            self.assertEqual(self._detect(events, home), [])


class WindowFallbackTests(unittest.TestCase):
    """No shadow log: yesterday-vs-today comparison inside the window itself."""

    def _detect(self, events, collector_status=None):
        with tempfile.TemporaryDirectory() as tmp:
            return detect_silent_sources(
                events,
                collector_status if collector_status is not None else {},
                datetime(2026, 3, 9, 0, 0, tzinfo=UTC),
                home=Path(tmp),
            )

    def test_source_active_yesterday_silent_today_alarms(self):
        events = [
            _event("Cursor (agent)", "2026-03-09"),
            _event("Cursor", "2026-03-09"),
            _event("Cursor", "2026-03-10"),
        ]
        findings = self._detect(events)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source, "Cursor (agent)")
        self.assertEqual(findings[0].baseline, "window")
        self.assertEqual(findings[0].scope, "last-day")

    def test_single_day_window_cannot_self_baseline(self):
        events = [_event("Cursor", "2026-03-09")]
        self.assertEqual(self._detect(events), [])

    def test_no_alarm_when_last_day_is_idle_for_everyone(self):
        events = [
            _event("Cursor (agent)", "2026-03-09"),
            _event("Cursor", "2026-03-09"),
        ]
        self.assertEqual(self._detect(events), [])

    def test_disabled_source_skipped_in_fallback(self):
        events = [
            _event("Claude Desktop (Code)", "2026-03-09"),
            _event("Claude Desktop", "2026-03-09"),
            _event("Claude Desktop", "2026-03-10"),
        ]
        status = {
            "Claude Desktop (Code)": {"enabled": False, "reason": "off", "events": 0}
        }
        self.assertEqual(self._detect(events, status), [])

    def test_fallback_requires_family_sibling_on_silent_day(self):
        # Windsurf (no sibling stream) idle on the last day while Cursor works:
        # normal tool choice, not an anomaly.
        events = [
            _event("Windsurf", "2026-03-09"),
            _event("Cursor", "2026-03-09"),
            _event("Cursor", "2026-03-10"),
        ]
        self.assertEqual(self._detect(events), [])


class CollectorStatusPatchTests(unittest.TestCase):
    def test_marks_existing_and_creates_missing_entries(self):
        status = {"Cursor": {"enabled": True, "reason": "", "events": 5}}
        findings = [
            SilentSourceFinding(
                source="Cursor (agent)",
                last_active="2026-03-09",
                baseline="shadow-log",
                baseline_days_active=3,
                scope="window",
            )
        ]
        apply_liveness_to_collector_status(status, findings)
        self.assertIn("Cursor (agent)", status)
        liveness = status["Cursor (agent)"]["liveness"]
        self.assertEqual(liveness["state"], "silent")
        self.assertEqual(liveness["last_active"], "2026-03-09")
        self.assertEqual(liveness["baseline"], "shadow-log")
        # Untouched collectors gain no liveness field.
        self.assertNotIn("liveness", status["Cursor"])


class WarningLineTests(unittest.TestCase):
    def test_lines_name_source_and_point_to_doctor(self):
        findings = [
            SilentSourceFinding(
                source="Cursor (agent)",
                last_active="2026-03-09",
                baseline="shadow-log",
                baseline_days_active=3,
                scope="window",
            )
        ]
        lines = silent_source_warning_lines(findings)
        self.assertEqual(len(lines), 1)
        self.assertIn("Cursor (agent)", lines[0])
        self.assertIn("gittan doctor", lines[0])


class EventsBySourceDayTests(unittest.TestCase):
    def test_counts_by_source_and_day(self):
        events = [
            _event("Cursor", "2026-03-09"),
            _event("Cursor", "2026-03-09", hour=12),
            _event("Chrome", "2026-03-10"),
            {"source": "Broken", "timestamp": "not-a-datetime"},
        ]
        self.assertEqual(
            events_by_source_day(events),
            {
                "Cursor": {"2026-03-09": 2},
                "Chrome": {"2026-03-10": 1},
            },
        )


class DoctorLivenessRowTests(unittest.TestCase):
    class _FakeTable:
        def __init__(self):
            self.rows: list[tuple[str, str, str]] = []

        def add_row(self, *cells):
            self.rows.append(tuple(cells))

    def _rows(self, home: Path, today: date):
        from core.doctor_liveness_rows import add_source_liveness_rows

        table = self._FakeTable()
        add_source_liveness_rows(
            table,
            home=home,
            ok_icon="OK",
            warn_icon="WARN",
            na_icon="NA",
            style_muted="dim",
            today=today,
        )
        return table.rows

    def test_no_store_yields_single_na_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._rows(Path(tmp), date(2026, 3, 10))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "Source liveness")
        self.assertEqual(rows[0][1], "NA")

    def test_recent_source_ok_and_quiet_source_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_shadow_records(
                home,
                [
                    _shadow_record("Cursor (agent)", "2026-03-10"),
                    _shadow_record("Windsurf", "2026-03-01"),
                ],
            )
            rows = self._rows(home, date(2026, 3, 10))
        by_label = {row[0]: row for row in rows}
        self.assertEqual(by_label["Cursor (agent)"][1], "OK")
        self.assertIn("Liveness:", by_label["Cursor (agent)"][2])
        self.assertEqual(by_label["Windsurf"][1], "WARN")
        self.assertIn("gone quiet", by_label["Windsurf"][2])


if __name__ == "__main__":
    unittest.main()
