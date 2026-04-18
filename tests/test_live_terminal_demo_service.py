"""Tests for live terminal demo session + exec service (P1)."""

from __future__ import annotations

import json
import unittest

from core.live_terminal.contract import DEMO_SANDBOX_DENIED_MESSAGE
from core.live_terminal.service import DemoSessionStore, demo_exec_line


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


    def test_session_store_is_thread_safe_concurrent_creates(self):
        """New in PR: DemoSessionStore uses threading.Lock; concurrent creates must not raise."""
        import threading

        store = DemoSessionStore()
        created_ids: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_session():
            try:
                sid = store.create()
                with lock:
                    created_ids.append(sid)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=create_session) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Errors during concurrent create: {errors}")
        self.assertEqual(len(created_ids), 20)
        # All session IDs should be unique
        self.assertEqual(len(set(created_ids)), 20)

    def test_session_store_valid_is_thread_safe(self):
        """valid() calls concurrent with create() must not raise."""
        import threading

        store = DemoSessionStore()
        sid = store.create()
        results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def check_valid():
            try:
                result = store.valid(sid)
                with lock:
                    results.append(result)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=check_valid) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Errors during concurrent valid(): {errors}")
        self.assertTrue(all(results))

    def test_session_expires_after_ttl(self):
        """Sessions with TTL=0 are immediately expired on next create/valid call."""
        import time

        store = DemoSessionStore(ttl_seconds=0)
        sid = store.create()
        # Give monotonic time a chance to advance
        time.sleep(0.01)
        # valid() triggers purge; session should now be expired
        self.assertFalse(store.valid(sid))

    def test_new_session_id_is_unique(self):
        """Each create() returns a distinct session token."""
        store = DemoSessionStore()
        ids = {store.create() for _ in range(10)}
        self.assertEqual(len(ids), 10)


if __name__ == "__main__":
    unittest.main()