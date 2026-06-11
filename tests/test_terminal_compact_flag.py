"""Terminal report --compact vs default full session trees."""

import unittest
from argparse import Namespace
from datetime import datetime, timezone

from outputs.terminal_preview import pick_session_preview_events

_BASE = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)


class TerminalCompactFlagTests(unittest.TestCase):
    def test_default_shows_all_session_events(self):
        session = [
            {"source": "Cursor", "local_ts": _BASE, "project": "P", "detail": "git noise"},
            {"source": "GitHub", "local_ts": _BASE, "project": "P", "detail": "push"},
        ]
        args = Namespace(compact=False, all_events=False)
        use_compact = getattr(args, "compact", False) and not getattr(args, "all_events", False)
        display = pick_session_preview_events(session, ["Cursor"]) if use_compact else session
        self.assertEqual(len(display), 2)

    def test_compact_filters_cursor_log_noise(self):
        session = [
            {"source": "Cursor", "local_ts": _BASE, "project": "P", "detail": "hooks.json — noise"},
            {"source": "GitHub", "local_ts": _BASE, "project": "P", "detail": "push"},
        ]
        args = Namespace(compact=True, all_events=False)
        use_compact = getattr(args, "compact", False) and not getattr(args, "all_events", False)
        display = pick_session_preview_events(session, ["Cursor"]) if use_compact else session
        self.assertEqual(len(display), 1)
        self.assertEqual(display[0]["source"], "GitHub")


if __name__ == "__main__":
    unittest.main()
