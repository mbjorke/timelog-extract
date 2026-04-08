#!/usr/bin/env python3
"""
Phase 0 helper: one-command friend trial runner.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = ROOT / "timelog_projects.example.json"
LOCAL_CONFIG = ROOT / "timelog_projects.json"


def run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def ensure_python() -> None:
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9+ is required.")


def ensure_config() -> None:
    if LOCAL_CONFIG.exists():
        return
    shutil.copy2(EXAMPLE_CONFIG, LOCAL_CONFIG)
    print(f"Created {LOCAL_CONFIG.name} from example. Edit it before full use.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a zero-friction friend trial.")
    parser.add_argument("--today", action="store_true", help="Run only for today.")
    parser.add_argument("--invoice-pdf", action="store_true", help="Also build invoice PDF.")
    args = parser.parse_args()

    ensure_python()
    ensure_config()

    cmd = [sys.executable, "timelog_extract.py", "--source-summary"]
    if args.today:
        cmd.append("--today")
    if args.invoice_pdf:
        cmd.append("--invoice-pdf")

    print("Running:", " ".join(cmd))
    code = run(cmd)
    if code != 0:
        print("Trial run failed. Please share the terminal output with the maintainer.")
    else:
        print("Trial run completed.")
        print("Please fill out friend_trial/FEEDBACK_TEMPLATE.md")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
