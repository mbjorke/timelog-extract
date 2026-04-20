"""HTTP integration tests for live terminal demo P1 server."""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

from core.live_terminal.http import make_demo_handler
from core.live_terminal.service import DemoSessionStore


class LiveTerminalDemoHttpTests(unittest.TestCase):
    def test_health_session_exec_flow(self):
        store = DemoSessionStore()
        handler = make_demo_handler(store)
        server = HTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            # Retry connection until server is ready
            for attempt in range(10):
                try:
                    with urllib.request.urlopen(f"{base}/demo/health", timeout=2) as r:  # noqa: S310
                        self.assertEqual(r.status, 200)
                        self.assertEqual(json.loads(r.read().decode())["status"], "ok")
                    break
                except (ConnectionRefusedError, urllib.error.URLError) as e:
                    if isinstance(e, urllib.error.HTTPError):
                        raise
                    if attempt < 9:
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    raise

            req = urllib.request.Request(f"{base}/demo/sessions", method="POST", data=b"")  # noqa: S310
            with urllib.request.urlopen(req, timeout=2) as r:  # noqa: S310
                self.assertEqual(r.status, 201)
                sid = json.loads(r.read().decode())["session_id"]

            body = json.dumps({"line": "gittan doctor"}).encode("utf-8")
            req = urllib.request.Request(  # noqa: S310
                f"{base}/demo/sessions/{sid}/exec",
                method="POST",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as r:  # noqa: S310
                self.assertEqual(r.status, 200)
                text = r.read().decode("utf-8")
                self.assertIn("Gittan Health Check", text)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()