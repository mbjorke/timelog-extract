"""Reconcile estimated project hours against invoiced ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from core.cli_ab_rule_suggestions import gather_ab_suggestions
from core.cli_experiments import variant_c_rules

UNCATEGORIZED = "Uncategorized"


@dataclass(frozen=True)
class ReconciliationResult:
    project: str
    actual_hours: float
    baseline_hours: float
    predicted_hours: float
    absolute_error: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "project": self.project,
            "actual_hours": round(self.actual_hours, 4),
            "baseline_hours": round(self.baseline_hours, 4),
            "predicted_hours": round(self.predicted_hours, 4),
            "absolute_error": round(self.absolute_error, 4),
        }


def evaluate_reconciliation(
    report,
    ground_truth_hours: dict[str, float],
) -> dict[str, Any]:
    """Compare baseline + A/B/C projections against invoiced ground truth."""
    uncategorized_events = [e for e in report.included_events if e.get("project") == UNCATEGORIZED]
    baseline_hours_map = {
        str(name): round(sum(float(day.get("hours", 0.0)) for day in days.values()), 6)
        for name, days in report.project_reports.items()
    }
    variants: dict[str, list[ReconciliationResult]] = {"baseline": [], "A": [], "B": [], "C": []}

    for project_name, actual_hours in sorted(ground_truth_hours.items()):
        base_hours = float(baseline_hours_map.get(project_name, 0.0))
        actual = float(actual_hours)
        variants["baseline"].append(
            ReconciliationResult(
                project=project_name,
                actual_hours=actual,
                baseline_hours=base_hours,
                predicted_hours=base_hours,
                absolute_error=abs(base_hours - actual),
            )
        )
        if not uncategorized_events:
            for key in ("A", "B", "C"):
                variants[key].append(
                    ReconciliationResult(
                        project=project_name,
                        actual_hours=actual,
                        baseline_hours=base_hours,
                        predicted_hours=base_hours,
                        absolute_error=abs(base_hours - actual),
                    )
                )
            continue

        opt_a, opt_b, prev_a, prev_b = gather_ab_suggestions(report, uncategorized_events, project_name)
        opt_c = variant_c_rules(opt_b)
        # We recompute C with same preview API by reusing report args.
        from core.rule_suggestions import preview_suggestion_impact

        exclude_list = [k.strip() for k in str(report.args.exclude or "").split(",") if k.strip()]
        prev_c = preview_suggestion_impact(
            uncategorized_events,
            report.profiles,
            project_name,
            opt_c,
            gap_minutes=int(report.args.gap_minutes),
            min_session_minutes=int(report.args.min_session),
            min_session_passive_minutes=int(report.args.min_session_passive),
            exclude_keywords=exclude_list,
            uncategorized_label=UNCATEGORIZED,
        )
        for key, preview in (("A", prev_a), ("B", prev_b), ("C", prev_c)):
            matched_hours = float(preview[1])
            predicted = base_hours + matched_hours
            variants[key].append(
                ReconciliationResult(
                    project=project_name,
                    actual_hours=actual,
                    baseline_hours=base_hours,
                    predicted_hours=predicted,
                    absolute_error=abs(predicted - actual),
                )
            )

    summaries: dict[str, dict[str, float]] = {}
    for key, rows in variants.items():
        errors = [row.absolute_error for row in rows]
        predicted_total = sum(row.predicted_hours for row in rows)
        actual_total = sum(row.actual_hours for row in rows)
        summaries[key] = {
            "mae": round(mean(errors), 4) if errors else 0.0,
            "total_predicted": round(predicted_total, 4),
            "total_actual": round(actual_total, 4),
            "total_delta": round(predicted_total - actual_total, 4),
        }
    winner = min(summaries.keys(), key=lambda v: summaries[v]["mae"])
    return {
        "winner": winner,
        "summaries": summaries,
        "rows": {key: [row.as_dict() for row in rows] for key, rows in variants.items()},
    }

