"""Deterministic A/B/C CLI experiment harness for CI reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.live_terminal.contract import is_allowlisted_demo_command
from core.rule_suggestions import RuleSuggestion, preview_suggestion_impact, split_ab_suggestions
from core.uncategorized_review import build_uncategorized_clusters

UNCATEGORIZED = "Uncategorized"


@dataclass(frozen=True)
class VariantMetrics:
    matched_events: int
    matched_hours: float
    uncategorized_delta: int
    events_classified_pct: float
    setup_seconds: float
    suggestion_acceptance_ratio: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "matched_events": self.matched_events,
            "matched_hours": self.matched_hours,
            "uncategorized_delta": self.uncategorized_delta,
            "events_classified_pct": self.events_classified_pct,
            "setup_seconds": self.setup_seconds,
            "suggestion_acceptance_ratio": self.suggestion_acceptance_ratio,
        }


@dataclass(frozen=True)
class VariantEvaluation:
    variant: str
    metrics: VariantMetrics
    passed: bool
    failed_thresholds: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "metrics": self.metrics.as_dict(),
            "passed": self.passed,
            "failed_thresholds": list(self.failed_thresholds),
        }


def _load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "name",
        "target_project",
        "profiles",
        "uncategorized_events",
        "command_sequence",
        "thresholds",
        "variant_inputs",
    }
    missing = sorted(required - set(data.keys()))
    if missing:
        raise ValueError(f"{path}: missing fixture keys: {', '.join(missing)}")
    for event in data.get("uncategorized_events", []):
        if not isinstance(event, dict):
            continue
        timestamp = event.get("timestamp")
        if isinstance(timestamp, str):
            event["timestamp"] = datetime.fromisoformat(timestamp)
    return data


def _validate_command_sequence(commands: list[str]) -> list[str]:
    invalid: list[str] = []
    for line in commands:
        if not is_allowlisted_demo_command(line):
            invalid.append(line)
    return invalid


def variant_c_rules(option_b: list[RuleSuggestion]) -> list[RuleSuggestion]:
    """Option C: balanced bundle between A and B.

    Keeps deterministic anchors and repeated terms, but drops single-event broad-only noise.
    """
    rules: list[RuleSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for suggestion in option_b:
        key = (suggestion.rule_type, suggestion.rule_value)
        if key in seen:
            continue
        seen.add(key)
        if suggestion.rule_type == "tracked_urls":
            rules.append(suggestion)
            continue
        if suggestion.cluster_count >= 2:
            rules.append(suggestion)
    return rules


def _evaluate_variant(
    variant: str,
    rules: list[RuleSuggestion],
    uncategorized_events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    target_project: str,
    thresholds: dict[str, float],
    variant_inputs: dict[str, Any],
) -> VariantEvaluation:
    matched_events, matched_hours, unc_delta = preview_suggestion_impact(
        uncategorized_events,
        profiles,
        target_project,
        rules,
        gap_minutes=15,
        min_session_minutes=15,
        min_session_passive_minutes=5,
        exclude_keywords=[],
        uncategorized_label=UNCATEGORIZED,
    )
    total_events = max(1, len(uncategorized_events))
    events_classified_pct = round(matched_events / total_events, 4)
    setup_seconds = float(variant_inputs.get("setup_seconds", {}).get(variant, 0.0))
    acceptance_ratio = float(variant_inputs.get("suggestion_acceptance_ratio", {}).get(variant, 0.0))

    metrics = VariantMetrics(
        matched_events=matched_events,
        matched_hours=matched_hours,
        uncategorized_delta=unc_delta,
        events_classified_pct=events_classified_pct,
        setup_seconds=setup_seconds,
        suggestion_acceptance_ratio=acceptance_ratio,
    )

    failed: list[str] = []
    if metrics.events_classified_pct < float(thresholds.get("events_classified_pct_min", 0.0)):
        failed.append("events_classified_pct_min")
    if metrics.suggestion_acceptance_ratio < float(thresholds.get("suggestion_acceptance_ratio_min", 0.0)):
        failed.append("suggestion_acceptance_ratio_min")
    if metrics.setup_seconds > float(thresholds.get("setup_seconds_max", 999999.0)):
        failed.append("setup_seconds_max")
    if metrics.matched_hours < float(thresholds.get("matched_hours_min", 0.0)):
        failed.append("matched_hours_min")
    return VariantEvaluation(
        variant=variant,
        metrics=metrics,
        passed=not failed,
        failed_thresholds=tuple(failed),
    )


def run_fixture(path: Path) -> dict[str, Any]:
    fixture = _load_fixture(path)
    invalid = _validate_command_sequence([str(x) for x in fixture["command_sequence"]])
    if invalid:
        raise ValueError(f"{path}: non-allowlisted demo commands in command_sequence: {invalid}")

    target_project = str(fixture["target_project"])
    profiles = [p for p in fixture["profiles"] if isinstance(p, dict)]
    uncategorized_events = [e for e in fixture["uncategorized_events"] if isinstance(e, dict)]
    clusters = build_uncategorized_clusters(
        uncategorized_events,
        max_clusters=50,
        samples_per_cluster=3,
    )
    option_a, option_b = split_ab_suggestions(clusters, profiles, target_project)
    option_c = variant_c_rules(option_b)

    thresholds = dict(fixture["thresholds"])
    variant_inputs = dict(fixture["variant_inputs"])
    evaluations = [
        _evaluate_variant(
            variant,
            rules,
            uncategorized_events,
            profiles,
            target_project,
            thresholds,
            variant_inputs,
        )
        for variant, rules in (("A", option_a), ("B", option_b), ("C", option_c))
    ]
    winner = max(
        evaluations,
        key=lambda ev: (
            ev.passed,
            ev.metrics.events_classified_pct,
            ev.metrics.suggestion_acceptance_ratio,
            -ev.metrics.setup_seconds,
        ),
    )
    return {
        "fixture": fixture["name"],
        "target_project": target_project,
        "thresholds": thresholds,
        "results": [ev.as_dict() for ev in evaluations],
        "winner": winner.variant,
        "all_passed": all(ev.passed for ev in evaluations),
    }


def run_fixtures(fixtures_dir: Path) -> dict[str, Any]:
    fixture_paths = sorted(fixtures_dir.glob("*_fixture.json"))
    if not fixture_paths:
        raise ValueError(f"No *_fixture.json files found in {fixtures_dir}")
    payloads = [run_fixture(path) for path in fixture_paths]
    return {
        "fixtures": payloads,
        "strict_pass": all(p["all_passed"] for p in payloads),
    }

