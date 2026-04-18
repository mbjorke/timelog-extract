"""Live terminal demo P1 — session store and allowlisted exec (no shell, no subprocess)."""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Final, Tuple

from core.live_terminal.contract import (
    DEMO_SANDBOX_DENIED_MESSAGE,
    validate_demo_command,
)
from core.live_terminal.stub_output import demo_stub_output

SESSION_TTL_SECONDS: Final[int] = 120


@dataclass
class DemoSession:
    created: float


@dataclass
class DemoSessionStore:
    """In-memory sessions with lazy TTL expiry (thread-safe)."""

    _sessions: Dict[str, DemoSession] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    ttl_seconds: int = SESSION_TTL_SECONDS

    def create(self) -> str:
        with self._lock:
            self._purge_expired()
            sid = secrets.token_urlsafe(16)
            self._sessions[sid] = DemoSession(created=time.monotonic())
            return sid

    def valid(self, session_id: str) -> bool:
        with self._lock:
            self._purge_expired()
            return session_id in self._sessions

    def _purge_expired(self) -> None:
        now = time.monotonic()
        dead = [sid for sid, s in self._sessions.items() if now - s.created > self.ttl_seconds]
        for sid in dead:
            del self._sessions[sid]


def demo_exec_line(store: DemoSessionStore, session_id: str, line: str) -> Tuple[int, str, str]:
    """Execute one demo line. Returns (http_status, content_type, body)."""
    if not store.valid(session_id):
        return 404, "application/json", json.dumps({"error": "session not found or expired"})
    allowed, msg = validate_demo_command(line)
    if not allowed:
        return 400, "application/json", json.dumps({"error": msg or DEMO_SANDBOX_DENIED_MESSAGE})
    try:
        out = demo_stub_output(line)
    except ValueError as exc:
        return 500, "application/json", json.dumps({"error": str(exc)})
    return 200, "text/plain; charset=utf-8", out

