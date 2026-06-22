"""Engine-agnostic evidence record contract for the local evidence shadow log.

This is the anti-corner asset from `docs/specs/local-evidence-shadow-log.md`
and `docs/task-prompts/local-evidence-shadow-log-slice1-task.md`: a versioned,
storage-independent record so JSONL today and SQLite/DuckDB later read the same
events without migration.

Key decision (locked): the ``fingerprint`` is computed on the *immutable
observation* (``source`` + UTC ``observed_at`` + ``detail``) and **excludes**
project classification. ``project_at_capture`` is stored as mutable metadata, so
reclassifying an event never fabricates a "new" record or breaks dedup.

This module is pure: no IO, no durable store. Persisting records is a later
slice (durable capture); slice 1 only defines and measures the contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.sources import get_source_role

EVIDENCE_SCHEMA_VERSION = 1

# Truncated SHA-256, consistent with existing short-hash usage in the codebase:
# enough collision resistance at the expected volume while staying readable.
_FINGERPRINT_LENGTH = 16

# Field separator unlikely to appear in source/detail text, so the fingerprint
# basis is unambiguous across its three parts.
_FIELD_SEP = "\x1f"


def _normalize_observed_at(observed_at: Any) -> str:
    """Canonical UTC ISO-8601 string for a datetime or pre-formatted timestamp."""
    if isinstance(observed_at, datetime):
        dt = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    s = str(observed_at or "").strip()
    # Normalize the RFC-3339 "Z" suffix to "+00:00" so a string timestamp and the
    # equivalent datetime yield the same fingerprint (the locked anti-corner rule).
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return s


def compute_evidence_fingerprint(source: Any, observed_at: Any, detail: Any) -> str:
    """Deterministic, project-independent fingerprint for an observation.

    Same (source, observed_at, detail) always yields the same fingerprint,
    regardless of how the event is later classified.
    """
    basis = _FIELD_SEP.join(
        [
            str(source or "").strip(),
            _normalize_observed_at(observed_at),
            str(detail or "").strip(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]


def compute_content_hash(record: Dict[str, Any]) -> str:
    """Tamper-evidence hash over the record at capture time.

    Excludes ``content_hash`` itself and the ``prev_hash`` chain pointer;
    everything else — including the mutable ``project_at_capture`` snapshot — is
    covered, so any post-capture modification (including authorised
    reclassification) is detectable and must refresh this hash. Chain linking is
    verified separately (prev_hash == previous content_hash).
    """
    payload = {k: v for k, v in record.items() if k not in ("content_hash", "prev_hash")}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evidence_record_from_event(
    event: Dict[str, Any],
    *,
    captured_at: Any,
    prev_hash: Optional[str] = None,
    source_provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Transform a collector/payload event dict into a full evidence record.

    Accepts both live collector events (``timestamp`` is a ``datetime``) and
    serialized payload events (``timestamp`` is an ISO string).
    """
    source = str(event.get("source", "") or "")
    observed_at = event.get("timestamp", event.get("observed_at"))
    detail = str(event.get("detail", "") or "")
    record: Dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "fingerprint": compute_evidence_fingerprint(source, observed_at, detail),
        "source": source,
        "source_provenance": source_provenance,
        "observed_at": _normalize_observed_at(observed_at),
        "captured_at": _normalize_observed_at(captured_at),
        "detail": detail,
        "project_at_capture": str(event.get("project", "") or ""),
        "source_role": get_source_role(source),
        "prev_hash": prev_hash,
    }
    record["content_hash"] = compute_content_hash(record)
    return record
