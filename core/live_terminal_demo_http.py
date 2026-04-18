"""Backward-compatible wrapper; prefer `core.live_terminal.http`."""

from core.live_terminal.http import make_demo_handler, serve_demo

__all__ = ["make_demo_handler", "serve_demo"]
