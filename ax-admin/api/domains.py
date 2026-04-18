"""
Domain registration endpoints — used by third-party Lovable/vibeops apps.

POST /api/v1/domains/check   — availability check (no auth needed, rate-limited)
POST /api/v1/domains         — register a domain
GET  /api/v1/domains/{name}  — get domain status
DELETE /api/v1/domains/{name} — cancel domain
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from api.deps import require_admin_or_api_key
from config import settings
from database import get_db
from models import APIKey, Domain
from services.dns_provider import get_dns_adapter
from services.registry import RegistrationRequest, get_registry_adapter

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


class AvailabilityRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def must_be_ax(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.endswith(".ax"):
            raise ValueError("Only .ax domains are supported")
        return v


class RegisterRequest(BaseModel):
    name: str
    registrant_name: str
    registrant_email: EmailStr
    registrant_org: Optional[str] = None
    registrant_country: str = "AX"
    years: int = 1

    @field_validator("name")
    @classmethod
    def must_be_ax(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.endswith(".ax"):
            raise ValueError("Only .ax domains are supported")
        return v

    @field_validator("years")
    @classmethod
    def valid_years(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("years must be between 1 and 10")
        return v


class DomainOut(BaseModel):
    name: str
    status: str
    registrant_name: str
    registrant_email: str
    registrant_org: Optional[str]
    registered_at: Optional[datetime]
    expires_at: Optional[datetime]
    nameserver1: str
    nameserver2: str

    model_config = {"from_attributes": True}


@router.post("/check")
def check_availability(body: AvailabilityRequest):
    registry = get_registry_adapter()
    available = registry.check_availability(body.name)
    return {"domain": body.name, "available": available}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DomainOut)
def register_domain(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    existing = db.query(Domain).filter(Domain.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Domain already registered")

    registry = get_registry_adapter()
    if not registry.check_availability(body.name):
        raise HTTPException(status_code=409, detail="Domain is not available")

    reg_result = registry.register(RegistrationRequest(
        domain_name=body.name,
        registrant_name=body.registrant_name,
        registrant_email=body.registrant_email,
        registrant_org=body.registrant_org,
        registrant_country=body.registrant_country,
        nameserver1=settings.nameserver1,
        nameserver2=settings.nameserver2,
        years=body.years,
    ))
    if not reg_result.success:
        raise HTTPException(status_code=502, detail=f"Registry error: {reg_result.error}")

    dns = get_dns_adapter()
    zone_result = dns.create_zone(body.name)

    domain = Domain(
        name=body.name,
        status="active",
        registrant_name=body.registrant_name,
        registrant_email=body.registrant_email,
        registrant_org=body.registrant_org,
        registrant_country=body.registrant_country,
        registered_at=datetime.utcnow(),
        expires_at=reg_result.expires_at,
        registry_reference=reg_result.registry_reference,
        dns_zone_id=zone_result.zone_id if zone_result.success else None,
        api_key_id=caller.id if caller else None,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)

    return _domain_out(domain)


@router.get("/{name}", response_model=DomainOut)
def get_domain(
    name: str,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(name.lower(), db, caller)
    return _domain_out(domain)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_domain(
    name: str,
    db: Session = Depends(get_db),
    caller: Optional[APIKey] = Depends(require_admin_or_api_key),
):
    domain = _get_authorized_domain(name.lower(), db, caller)

    if domain.registry_reference:
        get_registry_adapter().delete(domain.registry_reference)
    if domain.dns_zone_id:
        get_dns_adapter().delete_zone(domain.dns_zone_id)

    domain.status = "cancelled"
    db.commit()


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_authorized_domain(name: str, db: Session, caller: Optional[APIKey]) -> Domain:
    domain = db.query(Domain).filter(Domain.name == name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    # Admin (caller=None) can see all; API key callers only see their own domains
    if caller and domain.api_key_id != caller.id:
        raise HTTPException(status_code=403, detail="Not authorized for this domain")
    return domain


def _domain_out(domain: Domain) -> DomainOut:
    return DomainOut(
        name=domain.name,
        status=domain.status,
        registrant_name=domain.registrant_name,
        registrant_email=domain.registrant_email,
        registrant_org=domain.registrant_org,
        registered_at=domain.registered_at,
        expires_at=domain.expires_at,
        nameserver1=settings.nameserver1,
        nameserver2=settings.nameserver2,
    )
