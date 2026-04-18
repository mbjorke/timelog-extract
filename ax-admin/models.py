from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    key_prefix = Column(String(12), nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    domains = relationship("Domain", back_populates="api_key")


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    # pending | active | expired | cancelled
    status = Column(String(20), default="pending")

    registrant_name = Column(String(200), nullable=False)
    registrant_email = Column(String(200), nullable=False)
    registrant_org = Column(String(200), nullable=True)
    registrant_country = Column(String(2), default="AX")

    registered_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Reference returned by the .ax registry on successful registration
    registry_reference = Column(String(100), nullable=True)
    # DNS zone ID from the DNS provider (e.g. Cloudflare)
    dns_zone_id = Column(String(100), nullable=True)

    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_key = relationship("APIKey", back_populates="domains")
    dns_records = relationship("DNSRecord", back_populates="domain", cascade="all, delete-orphan")


class DNSRecord(Base):
    __tablename__ = "dns_records"

    id = Column(Integer, primary_key=True)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)

    # A | AAAA | CNAME | MX | TXT | NS
    record_type = Column(String(10), nullable=False)
    # "@" for root, "www" for www.domain.ax, etc.
    name = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    ttl = Column(Integer, default=3600)
    priority = Column(Integer, nullable=True)  # MX only

    # Cloudflare (or other provider) record ID for updates/deletes
    provider_record_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = relationship("Domain", back_populates="dns_records")
