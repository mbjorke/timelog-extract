"""Read-only volume & footprint measurement for the evidence shadow log.

Slice 1, item 2 (`docs/task-prompts/local-evidence-shadow-log-slice1-task.md`):
measure how much durable evidence the shadow log would actually hold, then
recommend a storage engine on data instead of guessing. Pure functions only —
no durable store is created here (the spike is read-only by construction).

Design note (measure, don't assume): record sizes are *measured* by serializing
real evidence records, not assumed from a fixed bytes-per-event guess. Only the
columnar compression ratio for the tiered option remains an estimate, and it is
labeled as such. The engine threshold is provisional and meant to be calibrated
from real spike runs — see PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.evidence_record import EVIDENCE_SCHEMA_VERSION, evidence_record_from_event

# Provisional gate, deliberately generous: this slice exists to MEASURE real
# volume, so the threshold must not silently pre-decide the small-volume answer.
# Calibrate from real spike runs before treating it as a hard rule.
PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB = 50.0

# Estimated columnar+compression ratio of Parquet vs raw JSONL bytes. This is an
# estimate (not measured) — writing real Parquet is deferred to the durable slice.
PARQUET_COMPRESSION_ESTIMATE = 0.35

_JSONL_NEWLINE_BYTES = 1


def _record_bytes(record: Dict[str, Any]) -> int:
    """Serialized JSONL size of one evidence record, in bytes (incl. newline)."""
    encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    return len(encoded.encode("utf-8")) + _JSONL_NEWLINE_BYTES


def measure_evidence_volume(
    records: List[Dict[str, Any]],
    collector_status: Dict[str, Dict[str, Any]],
    *,
    days_in_range: int,
) -> Dict[str, Any]:
    """Per-source and total volume stats from real evidence records.

    ``records`` are evidence records built from the (already event-key-deduped)
    included events. ``collector_status`` supplies the raw pre-dedup counts each
    collector saw. Fingerprint cardinality is computed at the evidence layer
    (project-independent), so it can be lower than the record count when events
    differed only by project classification.

    Per-source rows are keyed by the event *source label* (what actually gets
    stored), and the role is derived from that label. ``raw_collected`` is the
    collector status count, attached only on an exact name match — a single
    collector can emit a differently-named source (e.g. "Cursor (agent)"), so
    those rows report ``None`` rather than a misleading ``0``. The authoritative
    raw total is summed directly from ``collector_status`` and is independent of
    this name join.
    """
    days = max(int(days_in_range), 1)
    per_source: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        name = rec.get("source", "")
        bucket = per_source.setdefault(
            name,
            {
                "raw_collected": None,
                "evidence_records": 0,
                "source_role": rec.get("source_role", ""),
                "_fingerprints": set(),
                "_total_bytes": 0,
            },
        )
        bucket["evidence_records"] += 1
        bucket["_fingerprints"].add(rec.get("fingerprint"))
        bucket["_total_bytes"] += _record_bytes(rec)

    total_records = 0
    total_bytes = 0
    all_fingerprints = 0
    for name, bucket in per_source.items():
        recs = bucket["evidence_records"]
        uniq = len(bucket.pop("_fingerprints"))
        tbytes = bucket.pop("_total_bytes")
        status = collector_status.get(name)
        if status and "events" in status:
            bucket["raw_collected"] = int(status["events"])
        bucket["unique_fingerprints"] = uniq
        bucket["avg_record_bytes"] = round(tbytes / recs, 1) if recs else 0.0
        total_records += recs
        total_bytes += tbytes
        all_fingerprints += uniq

    # Authoritative raw total: everything collectors reported, regardless of how
    # the events are later labeled. Independent of the per-source name join.
    raw_collected_total = sum(
        int((status or {}).get("events", 0)) for status in collector_status.values()
    )
    # Collector status names that never matched an event source label, surfaced
    # as a diagnostic instead of fabricating zero-record per-source rows.
    unmatched = sorted(
        name
        for name, status in collector_status.items()
        if name not in per_source and int((status or {}).get("events", 0))
    )

    measured_avg = round(total_bytes / total_records, 1) if total_records else 0.0
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "days_in_range": days,
        "per_source": dict(sorted(per_source.items())),
        "collector_status_unmatched": unmatched,
        "totals": {
            "raw_collected": raw_collected_total,
            "evidence_records": total_records,
            "unique_fingerprints": all_fingerprints,
            "dedup_ratio": round(all_fingerprints / raw_collected_total, 4)
            if raw_collected_total
            else 0.0,
            "records_per_day": round(total_records / days, 2),
            "measured_avg_record_bytes": measured_avg,
            "measured_total_bytes": total_bytes,
        },
    }


def project_storage_footprint(measurement: Dict[str, Any]) -> Dict[str, Any]:
    """Project daily/yearly footprint from the MEASURED per-day record rate."""
    totals = measurement["totals"]
    records_per_day = float(totals["records_per_day"])
    avg_bytes = float(totals["measured_avg_record_bytes"])
    daily_jsonl_mb = records_per_day * avg_bytes / 1_000_000.0
    daily_parquet_mb = daily_jsonl_mb * PARQUET_COMPRESSION_ESTIMATE
    return {
        "records_per_day": round(records_per_day, 2),
        "measured_avg_record_bytes": round(avg_bytes, 1),
        "daily_jsonl_mb": round(daily_jsonl_mb, 4),
        "daily_parquet_mb_estimate": round(daily_parquet_mb, 4),
        "yearly_jsonl_mb": round(daily_jsonl_mb * 365, 2),
        "yearly_parquet_mb_estimate": round(daily_parquet_mb * 365, 2),
        "parquet_compression_estimate": PARQUET_COMPRESSION_ESTIMATE,
    }


def recommend_engine(
    footprint: Dict[str, Any],
    *,
    threshold_daily_mb: float = PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB,
) -> Dict[str, Any]:
    """Recommend a storage engine, surfacing the numbers the decision rests on."""
    daily_mb = float(footprint["daily_jsonl_mb"])
    over = daily_mb >= float(threshold_daily_mb)
    recommended = "tiered_parquet_duckdb" if over else "jsonl"
    if over:
        reasoning = (
            f"Measured ~{daily_mb:.3f} MB/day of durable evidence meets/exceeds the "
            f"provisional {threshold_daily_mb:g} MB/day gate; prefer tiered append "
            "-> columnar Parquet read by embedded DuckDB. pg_duckdb is still ruled "
            "out (server breaks local-first)."
        )
    else:
        reasoning = (
            f"Measured ~{daily_mb:.3f} MB/day of durable evidence is below the "
            f"provisional {threshold_daily_mb:g} MB/day gate; JSONL-first append-only "
            "stays inspectable and sufficient. The record contract keeps a later "
            "SQLite/DuckDB swap migration-free."
        )
    return {
        "recommended": recommended,
        "threshold_daily_mb": float(threshold_daily_mb),
        "measured_daily_jsonl_mb": round(daily_mb, 4),
        "reasoning": reasoning,
        "caveats": [
            "Measured over current report-level collectors only; a future granular "
            "(keystroke/edit/oplog) firehose is NOT measured here and would change "
            "the recommendation.",
            "Parquet figure uses a compression estimate, not a real Parquet write.",
            "Threshold is provisional; calibrate from real spike runs before "
            "treating it as a hard gate.",
        ],
    }


def _events_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for _day, day_block in (payload.get("days") or {}).items():
        events.extend(day_block.get("events") or [])
    return events


def _days_in_range(payload: Dict[str, Any]) -> int:
    rng = payload.get("range") or {}
    try:
        d_from = datetime.fromisoformat(str(rng["from"])).date()
        d_to = datetime.fromisoformat(str(rng["to"])).date()
    except (KeyError, ValueError):
        return max(len(payload.get("days") or {}), 1)
    return max((d_to - d_from).days + 1, 1)


def build_spike_report(
    payload: Dict[str, Any],
    *,
    captured_at: Optional[Any] = None,
    threshold_daily_mb: float = PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB,
) -> Dict[str, Any]:
    """Build the full read-only spike report from a truth payload dict.

    Pure: derives everything from ``payload`` in memory and writes nothing. The
    caller (the scripts/ runner) is responsible for any output file.
    """
    captured = captured_at if captured_at is not None else datetime.now()
    events = _events_from_payload(payload)
    records = [evidence_record_from_event(ev, captured_at=captured) for ev in events]
    collector_status = payload.get("collector_status") or {}
    measurement = measure_evidence_volume(
        records, collector_status, days_in_range=_days_in_range(payload)
    )
    footprint = project_storage_footprint(measurement)
    recommendation = recommend_engine(footprint, threshold_daily_mb=threshold_daily_mb)
    return {
        "schema": "timelog_extract.evidence_volume_spike",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "captured_at": captured.isoformat() if isinstance(captured, (datetime, date)) else str(captured),
        "measurement_period": payload.get("range") or {},
        "per_source": measurement["per_source"],
        "totals": measurement["totals"],
        "footprint_projection": footprint,
        "engine_recommendation": recommendation,
        "notes": [
            "Read-only measurement: no durable evidence store was created.",
            "See docs/task-prompts/local-evidence-shadow-log-slice1-task.md.",
        ],
    }
