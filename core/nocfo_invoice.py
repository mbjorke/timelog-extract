"""Turn approved (confirmed/edited) reported time into NoCFO draft-invoice payloads.

Only time the user already approved with ``gittan reported review`` / ``reported
add`` becomes an invoice row — raw observed sessions never do. One draft per
NoCFO customer contact; one row per project + day, so the customer sees the
same hour basis the user approved.

Pricing, unit and VAT live on the NoCFO **product** (``nocfo_product_id`` per
profile): the row copies them from the product read just before the draft is
created, and Gittan supplies only the hour count. Gittan does not do VAT. The receiver is the profile's ``nocfo_contact_id``.

A local append-only op-log (``<gittan data dir>/nocfo_oplog.jsonl``) records a
``pending`` row before each POST and ``created`` / ``rejected`` after it. The
latest row per contact + period decides: ``created`` and ``pending`` (an
uncertain outcome, e.g. a timeout) both block another POST until the user checks
NoCFO; only a definite HTTP rejection allows a retry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

OPLOG_FILENAME = "nocfo_oplog.jsonl"
UNCATEGORIZED = "Uncategorized"

# Required InvoiceRowRequest fields per NoCFO's OpenAPI schema: name, unit,
# amount (unit price), vat_rate, vat_code, product_count (quantity). They are
# copied from the referenced NoCFO product, so price and VAT stay owned by NoCFO;
# Gittan only supplies product_count (the approved hours) and a description.
PRODUCT_ROW_FIELDS = ("name", "unit", "vat_rate", "vat_code")
DEFAULT_PAYMENT_DAYS = 14


@dataclass(frozen=True)
class NocfoMapping:
    contact_id: int
    product_id: int


@dataclass
class DraftRow:
    project: str
    day: str
    hours: float


@dataclass
class DraftInvoice:
    contact_id: int
    date_from: str
    date_to: str
    invoicing_date: str
    rows: List[Tuple[DraftRow, int]] = field(default_factory=list)  # (row, product_id)

    @property
    def total_hours(self) -> float:
        return round(sum(r.hours for r, _ in self.rows), 2)

    @property
    def marker(self) -> str:
        """Idempotency key for the local op-log: one draft per contact + period."""
        return f"gittan:{self.contact_id}:{self.date_from}:{self.date_to}"

    @property
    def product_ids(self) -> List[int]:
        return sorted({product_id for _, product_id in self.rows})

    def payload(
        self,
        products: Dict[int, Dict[str, Any]],
        payment_condition_days: int = DEFAULT_PAYMENT_DAYS,
    ) -> Dict[str, Any]:
        """The exact JSON body sent to ``POST /v1/invoicing/{business}/invoice/``.

        ``products`` maps product id -> the NoCFO product record; name, unit,
        VAT-exclusive unit price and VAT come from there, never from Gittan.
        """
        rows = []
        for row, product_id in self.rows:
            product = products[product_id]
            entry = {key: product.get(key) for key in PRODUCT_ROW_FIELDS}
            unit_price = product.get("vat_exclusive_amount")
            entry["amount"] = unit_price if unit_price is not None else product.get("amount")
            entry["product"] = product_id
            entry["product_count"] = row.hours
            entry["description"] = f"{row.day} · {row.project}"
            rows.append(entry)
        return {
            "receiver": self.contact_id,
            "invoicing_date": self.invoicing_date,
            "payment_condition_days": int(payment_condition_days),
            "description": f"Hours {self.date_from} – {self.date_to}",
            "rows": rows,
        }


def _as_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_mapping(projects: Iterable[Dict[str, Any]]) -> Dict[str, NocfoMapping]:
    """Project name -> NoCFO contact + product, for profiles that declare both."""
    mapping: Dict[str, NocfoMapping] = {}
    for profile in projects or []:
        if not isinstance(profile, dict):
            continue
        name = str(profile.get("name") or "").strip()
        contact = _as_int(profile.get("nocfo_contact_id"))
        product = _as_int(profile.get("nocfo_product_id"))
        if not name:
            continue
        if contact is None or product is None:
            if profile.get("nocfo_contact_id") or profile.get("nocfo_product_id"):
                _LOGGER.warning("Project %r needs both nocfo_contact_id and nocfo_product_id", name)
            continue
        mapping[name] = NocfoMapping(contact_id=contact, product_id=product)
    return mapping


def build_drafts(
    approved: Dict[Tuple[str, str], float],
    mapping: Dict[str, NocfoMapping],
    date_from: str,
    date_to: str,
    *,
    project_filter: Optional[str] = None,
    invoicing_date: Optional[str] = None,
) -> Tuple[List[DraftInvoice], Dict[str, float]]:
    """Group approved ``{(project, day): hours}`` into one draft per contact.

    Returns ``(drafts, unmapped_hours_by_project)``. Uncategorized time and
    projects without a NoCFO mapping are reported, never invoiced.
    """
    inv_date = invoicing_date or date.today().isoformat()
    drafts: Dict[int, DraftInvoice] = {}
    unmapped: Dict[str, float] = {}
    for (project, day), hours in sorted(approved.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if not (date_from <= day <= date_to):
            continue
        if project_filter and project != project_filter:
            continue
        hours = round(float(hours), 2)
        if hours <= 0:
            continue
        target = mapping.get(project)
        if project == UNCATEGORIZED or target is None:
            unmapped[project] = round(unmapped.get(project, 0.0) + hours, 2)
            continue
        draft = drafts.setdefault(
            target.contact_id,
            DraftInvoice(target.contact_id, date_from, date_to, inv_date),
        )
        draft.rows.append((DraftRow(project, day, hours), target.product_id))
    return [drafts[k] for k in sorted(drafts)], unmapped


# --- local op-log ---------------------------------------------------------


def oplog_path(home: Optional[Path] = None) -> Path:
    from core.config import gittan_data_dir

    return gittan_data_dir(home) / OPLOG_FILENAME


def payload_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class NocfoOplogError(RuntimeError):
    """The local NoCFO op-log cannot be read completely."""


@dataclass
class NocfoOpRow:
    marker: str
    business: str
    invoice_id: str
    contact_id: int
    status: str  # pending | created | rejected
    total_hours: float
    payload_hash: str
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_ops(home: Optional[Path] = None) -> List[NocfoOpRow]:
    path = oplog_path(home)
    if not path.is_file():
        return []
    rows: List[NocfoOpRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = NocfoOpRow(**json.loads(line))
            if row.status not in OP_STATUSES:
                raise ValueError(f"unknown status {row.status!r}")
            rows.append(row)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            # Fail closed: this log is the only duplicate-draft guard, so a
            # damaged line must stop creation rather than be skipped.
            raise NocfoOplogError(
                f"NoCFO op-log {path} has an unreadable line ({exc}). Check NoCFO for "
                "drafts already created, then fix or remove that line before re-running."
            ) from None
    return rows


OP_STATUSES = {"pending", "created", "rejected"}


def blocking_markers(business: str, home: Optional[Path] = None) -> Dict[str, NocfoOpRow]:
    """Latest op per marker that blocks a new POST (``created`` or ``pending``)."""
    latest: Dict[str, NocfoOpRow] = {}
    for row in load_ops(home):
        if row.business == business:
            latest[row.marker] = row
    return {m: r for m, r in latest.items() if r.status in ("created", "pending")}


def record_op(row: NocfoOpRow, home: Optional[Path] = None) -> Path:
    """Append one op row and flush it to disk before returning."""
    path = oplog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(row), sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return path
