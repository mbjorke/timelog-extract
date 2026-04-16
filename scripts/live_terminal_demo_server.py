#!/usr/bin/env python3
"""Run the live terminal demo HTTP sketch (P1). See ``core.live_terminal_demo_http``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.live_terminal_demo_http import serve_demo


def main() -> None:
    p = argparse.ArgumentParser(description="Live terminal demo HTTP sketch (P1).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    print(f"live_terminal_demo_server listening on http://{args.host}:{args.port}", flush=True)
    print("POST /demo/sessions  |  POST /demo/sessions/<id>/exec  {\"line\": \"help\"}", flush=True)
    serve_demo(args.host, args.port)


if __name__ == "__main__":
    main()
