"""
Admin-only endpoints (require X-Admin-Key header).

GET    /api/v1/admin/domains           — list all registered domains
GET    /api/v1/admin/apikeys           — list API keys
POST   /api/v1/admin/apikeys           — create new API key
DELETE /api/v1/admin/apikeys/{id}      — revoke API key
"""

import hashlib
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import require_admin
from database import get_db
from models import APIKey, Domain

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── schemas ───────────────────────────────────────────────────────────────────

class DomainSummary(BaseModel):
    name: str
    status: str
    registrant_email: str
    registered_at: Optional[datetime]
    expires_at: Optional[datetime]
    api_key_name: Optional[str]

    model_config = {"from_attributes": True}


class APIKeyOut(BaseModel):
    id: int
    key_prefix: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    name: str


class APIKeyCreated(APIKeyOut):
    """Returned once on creation — the raw key is never stored."""
    raw_key: str


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/domains", response_model=List[DomainSummary], dependencies=[Depends(require_admin)])
def list_all_domains(db: Session = Depends(get_db)):
    domains = db.query(Domain).order_by(Domain.created_at.desc()).all()
    return [_domain_summary(d) for d in domains]


@router.get("/apikeys", response_model=List[APIKeyOut], dependencies=[Depends(require_admin)])
def list_api_keys(db: Session = Depends(get_db)):
    return db.query(APIKey).order_by(APIKey.created_at.desc()).all()


@router.post("/apikeys", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_api_key(body: APIKeyCreate, db: Session = Depends(get_db)):
    raw_key = f"ax_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=raw_key[:12],
        name=body.name,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return APIKeyCreated(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        raw_key=raw_key,
    )


@router.delete("/apikeys/{key_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
def revoke_api_key(key_id: int, db: Session = Depends(get_db)):
    api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    db.commit()


# ── helper ────────────────────────────────────────────────────────────────────

def _domain_summary(domain: Domain) -> DomainSummary:
    return DomainSummary(
        name=domain.name,
        status=domain.status,
        registrant_email=domain.registrant_email,
        registered_at=domain.registered_at,
        expires_at=domain.expires_at,
        api_key_name=domain.api_key.name if domain.api_key else None,
    )
