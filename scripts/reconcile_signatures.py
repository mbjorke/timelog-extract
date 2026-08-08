"""reconcile_signatures.py — the comparison model behind ``reconcile_snapshot.py``.

Pure functions over ``{project: hours}`` maps. No files, no clock, no report run,
so the classification rules can be pinned by tests without touching a data dir.

The central idea is a decomposition. For a baseline→comparison pair, the sum of
absolute per-project deltas (``gross``) splits *exactly* into ``|net| + 2 *
moved``: how much the period gained or lost, plus how much changed hands between
projects while the total stayed put. Those two numbers are what separate evidence
that vanished from evidence that was re-credited to a different customer, and the
two need different fixes — hence ``PairComparison.signature``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Hours = Dict[str, float]

STABLE = "STABLE"
EVIDENCE_DECAY = "EVIDENCE DECAY"
RE_ATTRIBUTION = "RE-ATTRIBUTION"
UPWARD_DRIFT = "UPWARD DRIFT"
MIXED = "MIXED"

# Share of gross change that must be reallocation before the leftover scale
# change is treated as noise instead of a second, separate finding.
DEFAULT_SHIFT_DOMINANCE = 0.75

SIGNATURE_MEANING = {
    STABLE: "the two views agree within tolerance",
    EVIDENCE_DECAY: "totals dropped together — evidence is gone, not moved (durability problem)",
    RE_ATTRIBUTION: "the split moved far more than the total did — same hours, different project (GH-544)",
    UPWARD_DRIFT: "totals grew without reallocation — better detection, or a keep-max ratchet (GH-543)",
    MIXED: "totals moved AND the split moved — treat as two findings, not one",
}

LEGEND = [
    "How to read this:",
    "  snapshot   hours the captured truth payload reported for this window, at the time.",
    "  observed   sum of the observed cache for this window. Keep-max, so an upper bound.",
    "  rescan     hours a fresh report produces for this window today.",
    "  '-'        the project is absent from that view entirely, itself a finding.",
    "  net        total change across the period (comparison minus baseline).",
    "  moved      hours that changed project while the period total stayed put.",
    "  gross      total absolute change; always equals |net| + 2*moved, so scale and",
    "             reallocation are measured separately and never double-counted.",
    "  SIGNATURE  which failure mode this is, and therefore which fix applies.",
]


@dataclass
class ProjectDelta:
    project: str
    baseline: float
    comparison: float

    @property
    def delta(self) -> float:
        return round(self.comparison - self.baseline, 6)

    @property
    def only_in(self) -> str:
        """"baseline", "comparison", or "" — a project present on one side only."""
        if self.baseline and not self.comparison:
            return "baseline"
        if self.comparison and not self.baseline:
            return "comparison"
        return ""


@dataclass
class PairComparison:
    """One baseline→comparison pair, decomposed into scale change and reallocation.

    ``gross`` (the sum of absolute per-project deltas) splits exactly into
    ``|net| + 2 * moved``. That identity is the whole instrument: ``net`` is how
    much the period gained or lost, ``moved`` is how much changed hands between
    projects while the total stayed put. A pure re-attribution has ``net == 0``
    and ``moved > 0``; pure decay has ``moved == 0`` and ``net < 0``.
    """

    baseline_label: str
    comparison_label: str
    rows: List[ProjectDelta] = field(default_factory=list)
    tolerance_hours: float = 0.0
    noise_floor_hours: float = 0.0
    shift_dominance: float = DEFAULT_SHIFT_DOMINANCE

    @property
    def baseline_total(self) -> float:
        return round(sum(r.baseline for r in self.rows), 6)

    @property
    def comparison_total(self) -> float:
        return round(sum(r.comparison for r in self.rows), 6)

    @property
    def net(self) -> float:
        return round(self.comparison_total - self.baseline_total, 6)

    @property
    def gross(self) -> float:
        return round(sum(abs(r.delta) for r in self.rows), 6)

    @property
    def moved(self) -> float:
        """Hours reallocated between projects, net of the period's own gain/loss."""
        return round(max(0.0, (self.gross - abs(self.net)) / 2.0), 6)

    @property
    def shift_share(self) -> float:
        """Fraction of gross change that is reallocation rather than scale (0..1)."""
        if self.gross <= 0:
            return 0.0
        return round(min(1.0, (2.0 * self.moved) / self.gross), 6)

    @property
    def net_pct(self) -> Optional[float]:
        if self.baseline_total <= 0:
            return None
        return round(100.0 * self.net / self.baseline_total, 2)

    @property
    def signature(self) -> str:
        """Name the failure mode, because decay and re-attribution need different fixes.

        Order matters. Reallocation is checked before scale: a period can lose a
        little *and* shuffle a lot, and the shuffle is the finding — that is
        exactly GH-544, where 6.25h became 5.83h while one project fell to a
        rounding error. ``shift_dominance`` is the share of gross change that
        must be reallocation before the residual scale change is treated as
        noise rather than a second finding.
        """
        if self.gross <= self.noise_floor_hours:
            return STABLE
        totals_held = abs(self.net) <= self.tolerance_hours
        if self.moved <= self.noise_floor_hours:
            if totals_held:
                return STABLE
            return UPWARD_DRIFT if self.net > 0 else EVIDENCE_DECAY
        if totals_held or self.shift_share >= self.shift_dominance:
            return RE_ATTRIBUTION
        return MIXED

    def movers(self, limit: int = 0) -> List[ProjectDelta]:
        ranked = sorted(
            (r for r in self.rows if abs(r.delta) > self.noise_floor_hours),
            key=lambda r: abs(r.delta),
            reverse=True,
        )
        return ranked[:limit] if limit else ranked


def compare_hours(
    baseline: Hours,
    comparison: Hours,
    *,
    baseline_label: str,
    comparison_label: str,
    tolerance_pct: float,
    noise_floor_hours: float,
    shift_dominance: float = DEFAULT_SHIFT_DOMINANCE,
) -> PairComparison:
    """Build a pair comparison over the union of project names in both views."""
    rows = [
        ProjectDelta(
            project=name,
            baseline=round(float(baseline.get(name, 0.0)), 6),
            comparison=round(float(comparison.get(name, 0.0)), 6),
        )
        for name in sorted(set(baseline) | set(comparison))
    ]
    baseline_total = sum(r.baseline for r in rows)
    tolerance_hours = max(noise_floor_hours, baseline_total * (tolerance_pct / 100.0))
    return PairComparison(
        baseline_label=baseline_label,
        comparison_label=comparison_label,
        rows=rows,
        tolerance_hours=round(tolerance_hours, 6),
        noise_floor_hours=noise_floor_hours,
        shift_dominance=shift_dominance,
    )


def redaction_map(views: Dict[str, Hours]) -> Dict[str, str]:
    """Stable ``project-NN`` aliases, ranked by the largest hours in any view."""
    weights: Dict[str, float] = {}
    for hours in views.values():
        for name, value in hours.items():
            weights[name] = max(weights.get(name, 0.0), float(value))
    ordered = sorted(weights, key=lambda n: (-weights[n], n))
    return {name: f"project-{i:02d}" for i, name in enumerate(ordered, start=1)}


def apply_redaction(hours: Hours, mapping: Dict[str, str]) -> Hours:
    return {mapping.get(name, name): value for name, value in hours.items()}


def _fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.2f}"


def render_text(
    window: Tuple[str, str],
    views: Dict[str, Hours],
    pairs: List[PairComparison],
    notes: List[str],
) -> str:
    lines: List[str] = []
    lines.append(f"reconcile_snapshot: {window[0]} .. {window[1]}")
    present = [name for name in ("snapshot", "observed", "rescan") if name in views]
    lines.append(f"views: {', '.join(present)}")
    for note in notes:
        lines.append(f"note: {note}")
    lines.append("")

    names = sorted(set().union(*(set(v) for v in views.values())) if views else set())
    width = max([len(n) for n in names] + [7])
    header = f"{'project'.ljust(width)}" + "".join(f"{name:>12}" for name in present)
    lines.append(header)
    lines.append("-" * len(header))
    for name in names:
        row = name.ljust(width)
        for view in present:
            value = views[view].get(name)
            row += f"{'-' if value is None else f'{value:.2f}':>12}"
        lines.append(row)
    lines.append("-" * len(header))
    total_row = "TOTAL".ljust(width)
    for view in present:
        total_row += f"{sum(views[view].values()):>12.2f}"
    lines.append(total_row)
    lines.append("")

    for pair in pairs:
        lines.extend(_render_pair(pair))
    lines.extend(LEGEND)
    return "\n".join(lines) + "\n"


def _render_pair(pair: PairComparison) -> List[str]:
    lines = [f"== {pair.baseline_label} -> {pair.comparison_label} =="]
    pct = "" if pair.net_pct is None else f" ({pair.net_pct:+.1f}%)"
    lines.append(
        f"  total: {_fmt(pair.baseline_total)}h -> {_fmt(pair.comparison_total)}h"
        f"  net {pair.net:+.2f}h{pct}"
    )
    lines.append(
        f"  moved between projects: {_fmt(pair.moved)}h"
        f"  (gross {_fmt(pair.gross)}h, shift share {pair.shift_share:.0%})"
    )
    lines.append(f"  SIGNATURE: {pair.signature} — {SIGNATURE_MEANING[pair.signature]}")
    movers = pair.movers(limit=10)
    if movers:
        lines.append("  largest movers:")
        for row in movers:
            flag = ""
            if row.only_in == "baseline":
                flag = "   [absent in " + pair.comparison_label + "]"
            elif row.only_in == "comparison":
                flag = "   [absent in " + pair.baseline_label + "]"
            lines.append(
                f"    {row.project}: {_fmt(row.baseline)}h -> {_fmt(row.comparison)}h"
                f"  ({row.delta:+.2f}){flag}"
            )
    lines.append("")
    return lines


def build_json(
    window: Tuple[str, str],
    views: Dict[str, Hours],
    pairs: List[PairComparison],
    notes: List[str],
) -> Dict[str, Any]:
    return {
        "window": {"from": window[0], "to": window[1]},
        "notes": notes,
        "views": {name: dict(sorted(hours.items())) for name, hours in views.items()},
        "pairs": [
            {
                "baseline": pair.baseline_label,
                "comparison": pair.comparison_label,
                "baseline_total": pair.baseline_total,
                "comparison_total": pair.comparison_total,
                "net": pair.net,
                "net_pct": pair.net_pct,
                "gross": pair.gross,
                "moved": pair.moved,
                "shift_share": pair.shift_share,
                "tolerance_hours": pair.tolerance_hours,
                "signature": pair.signature,
                "signature_meaning": SIGNATURE_MEANING[pair.signature],
                "movers": [
                    asdict(row) | {"delta": row.delta, "only_in": row.only_in}
                    for row in pair.movers(limit=10)
                ],
            }
            for pair in pairs
        ],
    }


