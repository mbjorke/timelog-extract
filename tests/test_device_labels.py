"""Display-only device suffixes — never change billing project identity."""

from __future__ import annotations

import unittest

from core.device_labels import (
    device_from_event,
    devices_for_events,
    display_project_label,
    ensure_live_device,
    short_device_token,
)
from core.sources import session_project_labels
from outputs.terminal_report_sections import events_by_project_for_device_labels


def _event(project: str, device: str | None = None) -> dict:
    ev = {"source": "Cursor", "project": project, "detail": "work"}
    if device is not None:
        ev["source_provenance"] = {"device": device}
    return ev


class DeviceLabelTests(unittest.TestCase):
    def test_short_token_strips_mdns_suffix(self):
        self.assertEqual(short_device_token("Mac.lan"), "Mac")
        self.assertEqual(short_device_token("iPhone.local"), "iPhone")
        self.assertEqual(short_device_token("laptop"), "laptop")

    def test_quiet_when_single_device(self):
        events = [_event("project-alpha", "Mac"), _event("project-alpha", "Mac")]
        self.assertEqual(display_project_label("project-alpha", events), "project-alpha")

    def test_multi_device_suffix(self):
        events = [
            _event("project-alpha", "Mac.lan"),
            _event("project-alpha", "iPhone"),
        ]
        self.assertEqual(
            display_project_label("project-alpha", events),
            "project-alpha (iPhone, Mac)",  # casefold sort
        )

    def test_never_invents_a_device(self):
        self.assertEqual(display_project_label("project-alpha", [_event("project-alpha")]), "project-alpha")

    def test_billing_key_unchanged_on_event(self):
        ev = _event("project-alpha", "Mac")
        display_project_label("project-alpha", [ev])
        self.assertEqual(ev["project"], "project-alpha")

    def test_session_labels_decorate_multi_device(self):
        events = [
            _event("project-alpha", "Mac"),
            _event("project-alpha", "iPhone"),
            _event("other", "Mac"),
        ]
        labels = session_project_labels(events)
        self.assertIn("project-alpha (iPhone, Mac)", labels)
        self.assertIn("other", labels)
        self.assertNotIn("other (Mac)", labels)

    def test_ensure_live_device_skips_existing(self):
        live = [_event("p", None), _event("p", "phone")]
        # first has no provenance key
        live[0].pop("source_provenance", None)
        out = ensure_live_device(live, "laptop")
        self.assertEqual(device_from_event(out[0]), "laptop")
        self.assertEqual(device_from_event(out[1]), "phone")

    def test_devices_for_events_dedupes(self):
        events = [_event("p", "Mac.lan"), _event("p", "Mac"), _event("p", "iPhone")]
        # Mac.lan → Mac and Mac collide on casefold after shorten… Mac.lan→Mac, Mac→Mac
        self.assertEqual(devices_for_events(events), ["iPhone", "Mac"])

    def test_additive_device_grouping_uses_primary_project(self):
        # Mixed-project session: alpha wins primary; beta event carries iPhone.
        start = end = "2026-07-26T10:00:00"
        session = (
            start,
            end,
            [
                _event("project-alpha", "Mac"),
                _event("project-alpha", "Mac"),
                _event("project-beta", "iPhone"),
            ],
        )
        overall_days = {"2026-07-26": {"sessions": [session]}}
        by_raw = events_by_project_for_device_labels(overall_days, additive_summary=False)
        self.assertEqual(sorted(by_raw), ["project-alpha", "project-beta"])
        self.assertEqual(devices_for_events(by_raw["project-alpha"]), ["Mac"])
        self.assertEqual(devices_for_events(by_raw["project-beta"]), ["iPhone"])

        by_add = events_by_project_for_device_labels(overall_days, additive_summary=True)
        self.assertEqual(list(by_add), ["project-alpha"])
        self.assertEqual(devices_for_events(by_add["project-alpha"]), ["iPhone", "Mac"])
        self.assertEqual(
            display_project_label(
                "project-alpha",
                devices=devices_for_events(by_add["project-alpha"]),
            ),
            "project-alpha (iPhone, Mac)",
        )


if __name__ == "__main__":
    unittest.main()
