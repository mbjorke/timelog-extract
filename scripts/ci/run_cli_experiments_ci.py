#!/usr/bin/env python3
"""Run deterministic A/B/C CLI experiment fixtures for CI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.calibration.experiments import run_fixtures


def _markdown_report(payload: dict) -> str:
    lines: list[str] = []
    lines.append("## CLI Experiment Scorecard")
    lines.append("")
    for fixture in payload.get("fixtures", []):
        lines.append(f"### Fixture: {fixture['fixture']}")
        lines.append(f"- Target project: `{fixture['target_project']}`")
        lines.append(f"- Winner: `{fixture['winner']}`")
        lines.append(f"- All variants passed thresholds: `{fixture['all_passed']}`")
        lines.append("")
        for result in fixture.get("results", []):
            metrics = result["metrics"]
            lines.append(
                f"- Variant `{result['variant']}`: "
                f"classified={metrics['events_classified_pct']:.2%}, "
                f"hours={metrics['matched_hours']}, "
                f"setup_s={metrics['setup_seconds']}, "
                f"acceptance={metrics['suggestion_acceptance_ratio']:.2%}, "
                f"pass={result['passed']}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-dir", default="tests/fixtures/experiments")
    parser.add_argument("--out-json", default="out/cli-experiments/scorecard.json")
    parser.add_argument("--out-md", default="out/cli-experiments/scorecard.md")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = run_fixtures(Path(args.fixtures_dir))
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(_markdown_report(payload), encoding="utf-8")
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    if args.strict and not payload.get("strict_pass", False):
        print("CLI experiments strict mode failed: one or more variants missed threshold.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

