"""Work-unit v2 spike acceptance evaluation (operator scorecard).

Compares a report's Project-hour review lines against an acceptance table
(JSON fixture or parsed markdown). Operator-specific files stay outside the
repo; only anonymized example fixtures are committed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from core.projects_lint import THIN_TERM_MAX, _looks_like_slug
from core.work_unit_classifier import build_work_units

UNCATEGORIZED = "Uncategorized"


@dataclass(frozen=True)
class AcceptanceLine:
    customer: str
    line: str
    expected_hours: float


@dataclass(frozen=True)
class AcceptanceTable:
    """Machine-readable acceptance window for the spike scorecard."""

    date_from: str
    date_to: str
    tolerance_hours: float
    lines: tuple[AcceptanceLine, ...]
    primary_uncategorized_max: Optional[float] = None
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "tolerance_hours": self.tolerance_hours,
            "primary_uncategorized_max": self.primary_uncategorized_max,
            "notes": self.notes,
            "lines": [
                {
                    "customer": row.customer,
                    "line": row.line,
                    "expected_hours": row.expected_hours,
                }
                for row in self.lines
            ],
        }


@dataclass(frozen=True)
class LineScore:
    customer: str
    line: str
    expected_hours: float
    actual_hours: float
    delta: float
    within_tolerance: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "customer": self.customer,
            "line": self.line,
            "expected_hours": round(self.expected_hours, 4),
            "actual_hours": round(self.actual_hours, 4),
            "delta": round(self.delta, 4),
            "within_tolerance": self.within_tolerance,
        }


@dataclass(frozen=True)
class SpikeVerdict:
    decision: str  # GO | NO-GO
    lines_ok: bool
    uncategorized_ok: bool
    no_slug_only_created: bool
    uncategorized_hours: float
    line_scores: tuple[LineScore, ...]
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "lines_ok": self.lines_ok,
            "uncategorized_ok": self.uncategorized_ok,
            "no_slug_only_created": self.no_slug_only_created,
            "uncategorized_hours": round(self.uncategorized_hours, 4),
            "line_scores": [row.as_dict() for row in self.line_scores],
            "reasons": list(self.reasons),
        }


def hours_by_project(report: Any) -> dict[str, float]:
    """Sum day hours per project/line from a ReportPayload or truth payload dict.

    Accepts:
    - ReportPayload-like objects with ``project_reports``
    - truth payload dicts from ``core.engine_api.run_report_payload`` (``projects`` totals)
    """
    if isinstance(report, Mapping):
        projects = report.get("projects")
        if isinstance(projects, Mapping) and projects:
            sample = next(iter(projects.values()))
            if isinstance(sample, (int, float)):
                return {
                    str(name): round(float(hours or 0.0), 6)
                    for name, hours in projects.items()
                }
        project_reports = report.get("project_reports") or {}
    else:
        project_reports = getattr(report, "project_reports", None) or {}
    out: dict[str, float] = {}
    for name, days in project_reports.items():
        total = 0.0
        if isinstance(days, Mapping):
            for day in days.values():
                if isinstance(day, Mapping):
                    total += float(day.get("hours", 0.0) or 0.0)
                else:
                    total += float(getattr(day, "hours", 0.0) or 0.0)
        out[str(name)] = round(total, 6)
    return out


def load_acceptance_json(path: Path | str) -> AcceptanceTable:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return acceptance_from_dict(data)


def acceptance_from_dict(data: Mapping[str, Any]) -> AcceptanceTable:
    lines_raw = data.get("lines") or data.get("targets") or []
    lines: list[AcceptanceLine] = []
    for row in lines_raw:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            AcceptanceLine(
                customer=str(row.get("customer") or "").strip(),
                line=str(row.get("line") or row.get("project") or "").strip(),
                expected_hours=float(row.get("expected_hours", row.get("hours", 0.0))),
            )
        )
    return AcceptanceTable(
        date_from=str(data.get("date_from") or data.get("from") or "").strip(),
        date_to=str(data.get("date_to") or data.get("to") or "").strip(),
        tolerance_hours=float(data.get("tolerance_hours", data.get("tolerance", 0.5))),
        lines=tuple(lines),
        primary_uncategorized_max=(
            float(data["primary_uncategorized_max"])
            if data.get("primary_uncategorized_max") is not None
            else None
        ),
        notes=str(data.get("notes") or ""),
    )


_MD_TABLE_ROW = re.compile(
    r"^\|\s*(?P<customer>[^|]+?)\s*\|\s*(?P<line>[^|]+?)\s*\|\s*(?P<hours>[^|]+?)\s*\|"
)


def parse_acceptance_markdown(text: str) -> AcceptanceTable:
    """Parse a minimal operator acceptance markdown into AcceptanceTable.

    Recognizes:
      - ``date_from:`` / ``date_to:`` / ``tolerance_hours:`` / ``primary_uncategorized_max:``
      - a markdown table with columns Customer | Line | Hours
    """
    meta: dict[str, str] = {}
    lines: list[AcceptanceLine] = []
    for raw in text.splitlines():
        line = raw.strip()
        lower = line.lower()
        for key in (
            "date_from",
            "date_to",
            "tolerance_hours",
            "primary_uncategorized_max",
            "notes",
        ):
            if lower.startswith(f"{key}:"):
                meta[key] = line.split(":", 1)[1].strip()
        match = _MD_TABLE_ROW.match(line)
        if not match:
            continue
        customer = match.group("customer").strip()
        line_name = match.group("line").strip()
        hours_raw = match.group("hours").strip().rstrip("hH")
        if customer.lower() in {"customer", "---", ":---", ":---:"} or set(customer) <= {"-"}:
            continue
        try:
            hours = float(hours_raw)
        except ValueError:
            continue
        lines.append(AcceptanceLine(customer=customer, line=line_name, expected_hours=hours))

    unc_max = meta.get("primary_uncategorized_max")
    return AcceptanceTable(
        date_from=meta.get("date_from", ""),
        date_to=meta.get("date_to", ""),
        tolerance_hours=float(meta.get("tolerance_hours", "0.5")),
        lines=tuple(lines),
        primary_uncategorized_max=float(unc_max) if unc_max not in (None, "") else None,
        notes=meta.get("notes", ""),
    )


def load_acceptance_file(path: Path | str) -> AcceptanceTable:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return acceptance_from_dict(json.loads(text))
    return parse_acceptance_markdown(text)


def _customer_map(profiles: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for profile in profiles:
        if not isinstance(profile, Mapping):
            continue
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        customer = str(profile.get("customer") or name).strip() or name
        out[name] = customer
    return out


def slug_only_lines_created(
    profiles: Sequence[Mapping[str, Any]],
    report_hours: Mapping[str, float],
) -> list[str]:
    """Return slug-named thin profiles that still appear as report lines with hours.

    After the work-unit classifier collapses thin duplicates, those names should
    not receive hours. Finding them in the report fails the anti-duplicate gate.
    """
    units = build_work_units(list(profiles))  # type: ignore[arg-type]
    unit_keys = {u.line_key for u in units}
    offenders: list[str] = []
    for profile in profiles:
        if not isinstance(profile, Mapping):
            continue
        name = str(profile.get("name") or "").strip()
        if not name or name in unit_keys:
            continue
        if not _looks_like_slug(name):
            continue
        terms = [t for t in (profile.get("match_terms") or []) if str(t).strip()]
        if len(terms) > THIN_TERM_MAX:
            continue
        if float(report_hours.get(name, 0.0) or 0.0) > 0.0:
            offenders.append(name)
    return offenders


def evaluate_spike(
    report: Any,
    acceptance: AcceptanceTable,
    *,
    profiles: Sequence[Mapping[str, Any]] | None = None,
    baseline_uncategorized: float | None = None,
) -> SpikeVerdict:
    """Score a report against acceptance; return GO / NO-GO with reasons."""
    hours = hours_by_project(report)
    profiles_list = list(profiles or getattr(report, "profiles", None) or [])
    customers = _customer_map(profiles_list)
    tolerance = float(acceptance.tolerance_hours)
    scores: list[LineScore] = []
    reasons: list[str] = []

    for row in acceptance.lines:
        actual = float(hours.get(row.line, 0.0) or 0.0)
        # If the line rolled under a different key, still compare by line name.
        delta = abs(actual - row.expected_hours)
        ok = delta <= tolerance
        if row.customer and row.line in customers and customers[row.line] != row.customer:
            ok = False
            reasons.append(
                f"line '{row.line}' customer is '{customers[row.line]}', "
                f"expected '{row.customer}'"
            )
        scores.append(
            LineScore(
                customer=row.customer,
                line=row.line,
                expected_hours=row.expected_hours,
                actual_hours=actual,
                delta=delta,
                within_tolerance=ok and delta <= tolerance,
            )
        )
        if not scores[-1].within_tolerance and f"line '{row.line}'" not in " ".join(reasons):
            reasons.append(
                f"line '{row.line}' hours {actual:.2f} vs expected "
                f"{row.expected_hours:.2f} (tol {tolerance})"
            )

    if not scores:
        reasons.append("acceptance table has no target lines")
    lines_ok = bool(scores) and all(s.within_tolerance for s in scores)
    unc = float(hours.get(UNCATEGORIZED, 0.0) or 0.0)
    unc_ok = True
    if acceptance.primary_uncategorized_max is not None:
        unc_ok = unc <= float(acceptance.primary_uncategorized_max) + 1e-9
        if not unc_ok:
            reasons.append(
                f"Uncategorized {unc:.2f}h exceeds max "
                f"{acceptance.primary_uncategorized_max:.2f}h"
            )
    elif baseline_uncategorized is not None and baseline_uncategorized > 0:
        # Soft gate when no explicit max: after must not exceed before.
        unc_ok = unc <= baseline_uncategorized + tolerance
        if not unc_ok:
            reasons.append(
                f"Uncategorized rose from {baseline_uncategorized:.2f}h to {unc:.2f}h"
            )

    offenders = slug_only_lines_created(profiles_list, hours) if profiles_list else []
    no_slug = not offenders
    if offenders:
        reasons.append(
            "slug-only duplicate line(s) still received hours: " + ", ".join(offenders)
        )

    decision = "GO" if (lines_ok and unc_ok and no_slug) else "NO-GO"
    return SpikeVerdict(
        decision=decision,
        lines_ok=lines_ok,
        uncategorized_ok=unc_ok,
        no_slug_only_created=no_slug,
        uncategorized_hours=unc,
        line_scores=tuple(scores),
        reasons=tuple(reasons),
    )


def scorecard_markdown(
    verdict: SpikeVerdict,
    *,
    title: str = "Work-unit v2 spike scorecard",
    baseline_uncategorized: float | None = None,
) -> str:
    lines = [f"## {title}", ""]
    lines.append(f"- Decision: `{verdict.decision}`")
    lines.append(f"- Uncategorized (after): `{verdict.uncategorized_hours:.2f}h`")
    if baseline_uncategorized is not None:
        lines.append(f"- Uncategorized (before / v1): `{baseline_uncategorized:.2f}h`")
    lines.append(f"- Lines within tolerance: `{verdict.lines_ok}`")
    lines.append(f"- No slug-only duplicate hours: `{verdict.no_slug_only_created}`")
    if verdict.reasons:
        lines.append("")
        lines.append("### Reasons")
        for reason in verdict.reasons:
            lines.append(f"- {reason}")
    lines.append("")
    lines.append("| Customer | Line | Expected | Actual | Delta | OK |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for row in verdict.line_scores:
        lines.append(
            f"| {row.customer} | {row.line} | {row.expected_hours:.2f} | "
            f"{row.actual_hours:.2f} | {row.delta:.2f} | "
            f"{'yes' if row.within_tolerance else 'no'} |"
        )
    lines.append("")
    lines.append(
        "_Operator-specific customers/hours belong in the local acceptance file; "
        "do not paste them into PR bodies._"
    )
    return "\n".join(lines) + "\n"
