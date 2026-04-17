"""stdlib HTTP server for live terminal demo P1 (sessions + exec, stub output)."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from core.live_terminal.service import DemoSessionStore, demo_exec_line

_EXEC_PATH = re.compile(r"^/demo/sessions/([^/]+)/exec/?$")
_MAX_BODY_BYTES = 64 * 1024


def make_demo_handler(store: DemoSessionStore) -> type[BaseHTTPRequestHandler]:
    class DemoTerminalHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path.rstrip("/") == "/demo/health":
                body = b'{"status":"ok"}\n'
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._cors()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path.rstrip("/") == "/demo/sessions":
                sid = store.create()
                body = json.dumps({"session_id": sid}).encode("utf-8")
                self.send_response(201)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._cors()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            m = _EXEC_PATH.match(path.rstrip("/"))
            if not m:
                self.send_error(404)
                return
            raw_len = self.headers.get("Content-Length")
            try:
                length = int(raw_len) if raw_len is not None else 0
            except ValueError:
                self._json_error(400, "invalid Content-Length")
                return
            if length < 0:
                self._json_error(400, "invalid Content-Length")
                return
            if length > _MAX_BODY_BYTES:
                self._json_error(413, "request body too large")
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._json_error(400, "invalid JSON body")
                return
            line = str(payload.get("line", ""))
            status, ctype, out = demo_exec_line(store, m.group(1), line)
            data = out.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self._cors()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json_error(self, status: int, message: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._cors()
            err = json.dumps({"error": message}).encode("utf-8")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    return DemoTerminalHandler


def serve_demo(host: str, port: int, *, store: Optional[DemoSessionStore] = None) -> None:
    st = store or DemoSessionStore()
    handler = make_demo_handler(st)
    server = HTTPServer((host, port), handler)
    server.serve_forever()

