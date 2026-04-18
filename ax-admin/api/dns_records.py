"""
DNS record management endpoints.

GET    /api/v1/domains/{name}/records           — list records
POST   /api/v1/domains/{name}/records           — add record
PUT    /api/v1/domains/{name}/records/{id}      — update record
DELETE /api/v1/domains/{name}/records/{id}      — delete record
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import require_admin_or_api_key
from database import get_db
from models import APIKey, DNSRecord, Domain
from services.dns_provider import DNSRecordData, get_dns_adapter

router = APIRouter(prefix="/api/v1/domains", tags=["dns"])

ALLOWED_TYPES = {"A", "AAAA", "CNAME", "MX", "TXT", "NS", "CAA"}


class RecordIn(BaseModel):
    record_type: str
    name: str
    value: str
    ttl: int = 3600
    priority: Optional[int] = None


class RecordOut(BaseModel):
    id: int
    record_type: str
    name: str
    value: str
    ttl: int
    priority: Optional[int]

    model_config = {"from_attributes": True}


@router.get("/{domain_name}/records", response_model=List[RecordOut])
def list_records(
    domain_name: str,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(domain_name.lower(), db, caller)
    return domain.dns_records


@router.post("/{domain_name}/records", status_code=status.HTTP_201_CREATED, response_model=RecordOut)
def add_record(
    domain_name: str,
    body: RecordIn,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(domain_name.lower(), db, caller)
    _validate_record_type(body.record_type)

    dns = get_dns_adapter()
    result = dns.add_record(
        domain.dns_zone_id or "no-zone",
        DNSRecordData(
            record_type=body.record_type.upper(),
            name=body.name,
            value=body.value,
            ttl=body.ttl,
            priority=body.priority,
        ),
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=f"DNS provider error: {result.error}")

    record = DNSRecord(
        domain_id=domain.id,
        record_type=body.record_type.upper(),
        name=body.name,
        value=body.value,
        ttl=body.ttl,
        priority=body.priority,
        provider_record_id=result.provider_record_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{domain_name}/records/{record_id}", response_model=RecordOut)
def update_record(
    domain_name: str,
    record_id: int,
    body: RecordIn,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(domain_name.lower(), db, caller)
    _validate_record_type(body.record_type)
    record = _get_record(record_id, domain.id, db)

    dns = get_dns_adapter()
    result = dns.update_record(
        domain.dns_zone_id or "no-zone",
        record.provider_record_id or "",
        DNSRecordData(
            record_type=body.record_type.upper(),
            name=body.name,
            value=body.value,
            ttl=body.ttl,
            priority=body.priority,
        ),
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=f"DNS provider error: {result.error}")

    record.record_type = body.record_type.upper()
    record.name = body.name
    record.value = body.value
    record.ttl = body.ttl
    record.priority = body.priority
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{domain_name}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    domain_name: str,
    record_id: int,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(domain_name.lower(), db, caller)
    record = _get_record(record_id, domain.id, db)

    if record.provider_record_id:
        get_dns_adapter().delete_record(
            domain.dns_zone_id or "no-zone",
            record.provider_record_id,
        )
    db.delete(record)
    db.commit()


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_authorized_domain(name: str, db: Session, caller: Optional[APIKey]) -> Domain:
    domain = db.query(Domain).filter(Domain.name == name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if caller and domain.api_key_id != caller.id:
        raise HTTPException(status_code=403, detail="Not authorized for this domain")
    return domain


def _get_record(record_id: int, domain_id: int, db: Session) -> DNSRecord:
    record = db.query(DNSRecord).filter(
        DNSRecord.id == record_id,
        DNSRecord.domain_id == domain_id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="DNS record not found")
    return record


def _validate_record_type(record_type: str) -> None:
    if record_type.upper() not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported record type '{record_type}'. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )
