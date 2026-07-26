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
        events = [_event("timelog-extract", "Mac"), _event("timelog-extract", "Mac")]
        self.assertEqual(display_project_label("timelog-extract", events), "timelog-extract")

    def test_multi_device_suffix(self):
        events = [
            _event("timelog-extract", "Mac.lan"),
            _event("timelog-extract", "iPhone"),
        ]
        self.assertEqual(
            display_project_label("timelog-extract", events),
            "timelog-extract (iPhone, Mac)",  # casefold sort
        )

    def test_never_invents_a_device(self):
        self.assertEqual(display_project_label("timelog-extract", [_event("timelog-extract")]), "timelog-extract")

    def test_billing_key_unchanged_on_event(self):
        ev = _event("timelog-extract", "Mac")
        display_project_label("timelog-extract", [ev])
        self.assertEqual(ev["project"], "timelog-extract")

    def test_session_labels_decorate_multi_device(self):
        events = [
            _event("timelog-extract", "Mac"),
            _event("timelog-extract", "iPhone"),
            _event("other", "Mac"),
        ]
        labels = session_project_labels(events)
        self.assertIn("timelog-extract (iPhone, Mac)", labels)
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


if __name__ == "__main__":
    unittest.main()
