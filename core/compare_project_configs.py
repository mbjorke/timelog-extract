"""Pure helpers to compare two truth payloads by project hours (config A vs B)."""

from __future__ import annotations

from typing import Any, List, Mapping, Tuple


def project_hours_table(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> List[Tuple[str, float, float, float]]:
    """Return rows: (project_name, hours_baseline, hours_candidate, delta_candidate_minus_baseline)."""
    pa = baseline.get("projects") or {}
    pb = candidate.get("projects") or {}
    if not isinstance(pa, dict) or not isinstance(pb, dict):
        raise TypeError("payload['projects'] must be a dict")
    names = sorted(set(pa) | set(pb), key=lambda s: (s.lower(), s))
    rows: List[Tuple[str, float, float, float]] = []
    for name in names:
        ha = float(pa.get(name, 0.0) or 0.0)
        hb = float(pb.get(name, 0.0) or 0.0)
        rows.append((name, ha, hb, round(hb - ha, 6)))
    return rows


def format_comparison_text(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    label_a: str = "baseline",
    label_b: str = "candidate",
) -> str:
    """Human-readable table: project hours, totals, event counts."""
    rows = project_hours_table(baseline, candidate)
    ta = baseline.get("totals") or {}
    tb = candidate.get("totals") or {}
    ha = float(ta.get("hours_estimated", 0.0) or 0.0)
    hb = float(tb.get("hours_estimated", 0.0) or 0.0)
    ea = int(ta.get("event_count", 0) or 0)
    eb = int(tb.get("event_count", 0) or 0)

    w = max(len(label_a), len(label_b), 9)
    colw = max(w, 12)
    lines: List[str] = []
    header = f"{'project':<32} {label_a:>{colw}} {label_b:>{colw}} {'Δ':>10}"
    lines.append(header)
    lines.append("-" * len(header))
    for name, a, b, d in rows:
        if abs(a) < 1e-9 and abs(b) < 1e-9 and abs(d) < 1e-9:
            continue
        lines.append(f"{name[:31]:<32} {a:>{colw}.4f} {b:>{colw}.4f} {d:>+10.4f}")
    lines.append("-" * len(header))
    lines.append(
        f"{'totals.hours_estimated':<32} {ha:>{colw}.4f} {hb:>{colw}.4f} {hb - ha:>+10.4f}"
    )
    lines.append(f"{'totals.event_count':<32} {ea:>{colw}} {eb:>{colw}} {eb - ea:>+10}")
    return "\n".join(lines) + "\n"
