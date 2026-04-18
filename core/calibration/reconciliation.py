"""Reconcile estimated project hours against invoiced ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from core.calibration.experiments import variant_c_rules
from core.cli_ab_rule_suggestions import gather_ab_suggestions
from core.rule_suggestions import preview_suggestion_impact

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


@dataclass(frozen=True)
class GroupReconciliationResult:
    group: str
    actual_hours: float
    predicted_hours: float
    absolute_error: float
    member_projects: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "actual_hours": round(self.actual_hours, 4),
            "predicted_hours": round(self.predicted_hours, 4),
            "absolute_error": round(self.absolute_error, 4),
            "member_projects": list(self.member_projects),
        }


def _group_rows_for_variant(
    variant_rows: list[ReconciliationResult],
    invoice_groups: dict[str, dict[str, Any]],
) -> list[GroupReconciliationResult]:
    """
    Builds group-level reconciliation rows by aggregating predicted hours of member projects defined in invoice_groups.
    
    Parameters:
    	variant_rows (list[ReconciliationResult]): Per-project reconciliation results to draw predicted hours from.
    	invoice_groups (dict[str, dict]): Mapping from group name to group config. Each config may contain:
    		- "projects": iterable of project names (strings) that belong to the group
    		- "actual_hours": numeric actual hours for the group (defaults to 0.0 if missing)
    
    Returns:
    	list[GroupReconciliationResult]: One result per invoice group that has at least one valid project, where each result contains the group's name, actual hours, summed predicted hours from member projects present in variant_rows, absolute error, and the tuple of member project names.
    """
    by_project = {row.project: row for row in variant_rows}
    out: list[GroupReconciliationResult] = []
    for group_name, config in sorted(invoice_groups.items()):
        projects = tuple(str(p) for p in (config.get("projects") or []) if str(p).strip())
        if not projects:
            continue
        actual = float(config.get("actual_hours", 0.0))
        predicted = sum(by_project.get(name).predicted_hours for name in projects if name in by_project)
        out.append(
            GroupReconciliationResult(
                group=group_name,
                actual_hours=actual,
                predicted_hours=predicted,
                absolute_error=abs(predicted - actual),
                member_projects=projects,
            )
        )
    return out


def evaluate_reconciliation(
    report,
    ground_truth_hours: dict[str, float],
    invoice_groups: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Compare baseline and A/B/C variant time allocations against invoiced ground-truth hours and pick the best-performing variant.
    
    Produces per-project reconciliation rows for each variant, per-variant summary metrics (mean absolute error, totals), optional invoice-grouped reconciliation and summaries, and selects a winner by MAE at project and (if provided) group levels.
    
    Parameters:
        report: Analyzer report object containing included events, project reports, profiles, and args used to generate suggestions.
        ground_truth_hours (dict[str, float]): Mapping of project name to invoiced (ground-truth) hours.
        invoice_groups (dict[str, dict[str, Any]] | None): Optional invoice group configuration mapping group name to group config (e.g., {"projects": [...], "hours": ...}). If provided, grouped reconciliation and grouped MAE are computed.
    
    Returns:
        dict[str, Any]: Structured reconciliation results with keys:
            - "winner": variant key with lowest project-level MAE.
            - "winner_grouped": variant key with lowest grouped MAE (or same as "winner" if no groups).
            - "primary_metric_mode": "grouped" if grouped summaries were computed, otherwise "project".
            - "primary_winner": chosen winner according to the primary metric mode.
            - "summaries": per-variant project-level metrics (mae, total_predicted, total_actual, total_delta).
            - "group_summaries": per-variant grouped metrics (empty if no invoice_groups).
            - "rows": per-variant list of per-project reconciliation row dicts.
            - "group_rows": per-variant list of per-group reconciliation row dicts (empty if no invoice_groups).
    """
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

        _opt_a, opt_b, prev_a, prev_b = gather_ab_suggestions(report, uncategorized_events, project_name)
        opt_c = variant_c_rules(opt_b)
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
    group_rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    group_summaries: dict[str, dict[str, float]] = {}
    if invoice_groups:
        for key, rows in variants.items():
            group_rows = _group_rows_for_variant(rows, invoice_groups)
            group_rows_by_variant[key] = [row.as_dict() for row in group_rows]
            errors = [row.absolute_error for row in group_rows]
            pred_total = sum(row.predicted_hours for row in group_rows)
            act_total = sum(row.actual_hours for row in group_rows)
            group_summaries[key] = {
                "mae": round(mean(errors), 4) if errors else 0.0,
                "total_predicted": round(pred_total, 4),
                "total_actual": round(act_total, 4),
                "total_delta": round(pred_total - act_total, 4),
            }
    winner_grouped = min(group_summaries.keys(), key=lambda v: group_summaries[v]["mae"]) if group_summaries else winner

    primary_mode = "grouped" if group_summaries else "project"
    primary_winner = winner_grouped if group_summaries else winner

    return {
        "winner": winner,
        "winner_grouped": winner_grouped,
        "primary_metric_mode": primary_mode,
        "primary_winner": primary_winner,
        "summaries": summaries,
        "group_summaries": group_summaries,
        "rows": {key: [row.as_dict() for row in rows] for key, rows in variants.items()},
        "group_rows": group_rows_by_variant,
    }

