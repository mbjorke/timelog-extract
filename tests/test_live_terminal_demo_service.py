"""Tests for live terminal demo session + exec service (P1)."""

from __future__ import annotations

import json
import unittest

from core.live_terminal_demo_contract import DEMO_SANDBOX_DENIED_MESSAGE
from core.live_terminal_demo_service import DemoSessionStore, demo_exec_line


class LiveTerminalDemoServiceTests(unittest.TestCase):
    def test_create_and_exec_help(self):
        store = DemoSessionStore()
        sid = store.create()
        status, ctype, body = demo_exec_line(store, sid, "help")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", ctype)
        self.assertIn("allowlisted", body)

    def test_exec_denied(self):
        store = DemoSessionStore()
        sid = store.create()
        status, ctype, body = demo_exec_line(store, sid, "rm -rf /")
        self.assertEqual(status, 400)
        self.assertIn("application/json", ctype)
        err = json.loads(body)
        self.assertEqual(err["error"], DEMO_SANDBOX_DENIED_MESSAGE)

    def test_exec_unknown_session(self):
        store = DemoSessionStore()
        status, _, body = demo_exec_line(store, "nope", "help")
        self.assertEqual(status, 404)
        err = json.loads(body)
        self.assertIn("error", err)


if __name__ == "__main__":
    unittest.main()
