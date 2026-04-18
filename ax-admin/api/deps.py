"""FastAPI dependency helpers for authentication."""

import hashlib
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import APIKey


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def require_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing X-Admin-Key header")


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> APIKey:
    """Validate Bearer <api-key> and return the matching APIKey row."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authorization: Bearer <key> header required")
    raw = authorization.removeprefix("Bearer ").strip()
    key_hash = _hash_key(raw)
    api_key = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.is_active.is_(True),
    ).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or revoked API key")
    from datetime import datetime
    api_key.last_used_at = datetime.utcnow()
    db.commit()
    return api_key


def require_admin_or_api_key(
    x_admin_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[APIKey]:
    """Accept either admin key or a valid Bearer API key."""
    if x_admin_key and x_admin_key == settings.admin_api_key:
        return None  # admin — no APIKey row needed
    if authorization:
        return require_api_key(authorization, db)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Provide X-Admin-Key or Authorization: Bearer <key>")
