"""
DNS provider adapter.

CloudflareDNSAdapter uses the Cloudflare v4 API to manage zones and records.
Set CLOUDFLARE_API_TOKEN (and optionally CLOUDFLARE_ACCOUNT_ID) in .env.

StubDNSAdapter is the fallback for local dev — it logs calls and returns
synthetic record IDs without touching any real DNS infrastructure.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

CF_BASE = "https://api.cloudflare.com/client/v4"


@dataclass
class DNSRecordData:
    record_type: str
    name: str
    value: str
    ttl: int = 3600
    priority: Optional[int] = None


@dataclass
class DNSZoneResult:
    success: bool
    zone_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DNSRecordResult:
    success: bool
    provider_record_id: Optional[str] = None
    error: Optional[str] = None


class DNSProviderAdapter(ABC):
    @abstractmethod
    def create_zone(self, domain_name: str) -> DNSZoneResult:
        pass

    @abstractmethod
    def delete_zone(self, zone_id: str) -> bool:
        pass

    @abstractmethod
    def add_record(self, zone_id: str, record: DNSRecordData) -> DNSRecordResult:
        pass

    @abstractmethod
    def update_record(self, zone_id: str, record_id: str, record: DNSRecordData) -> DNSRecordResult:
        pass

    @abstractmethod
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        pass


class CloudflareDNSAdapter(DNSProviderAdapter):
    def __init__(self, api_token: str, account_id: str = ""):
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._account_id = account_id

    def create_zone(self, domain_name: str) -> DNSZoneResult:
        payload: dict = {"name": domain_name, "type": "full"}
        if self._account_id:
            payload["account"] = {"id": self._account_id}
        with httpx.Client(timeout=15) as client:
            r = client.post(f"{CF_BASE}/zones", json=payload, headers=self._headers)
        data = r.json()
        if data.get("success"):
            return DNSZoneResult(success=True, zone_id=data["result"]["id"])
        err = str(data.get("errors", "unknown"))
        logger.error("Cloudflare create_zone failed: %s", err)
        return DNSZoneResult(success=False, error=err)

    def delete_zone(self, zone_id: str) -> bool:
        with httpx.Client(timeout=15) as client:
            r = client.delete(f"{CF_BASE}/zones/{zone_id}", headers=self._headers)
        return r.json().get("success", False)

    def add_record(self, zone_id: str, record: DNSRecordData) -> DNSRecordResult:
        payload: dict = {
            "type": record.record_type,
            "name": record.name,
            "content": record.value,
            "ttl": record.ttl,
        }
        if record.priority is not None:
            payload["priority"] = record.priority
        with httpx.Client(timeout=15) as client:
            r = client.post(f"{CF_BASE}/zones/{zone_id}/dns_records",
                            json=payload, headers=self._headers)
        data = r.json()
        if data.get("success"):
            return DNSRecordResult(success=True, provider_record_id=data["result"]["id"])
        err = str(data.get("errors", "unknown"))
        logger.error("Cloudflare add_record failed: %s", err)
        return DNSRecordResult(success=False, error=err)

    def update_record(self, zone_id: str, record_id: str, record: DNSRecordData) -> DNSRecordResult:
        payload: dict = {
            "type": record.record_type,
            "name": record.name,
            "content": record.value,
            "ttl": record.ttl,
        }
        if record.priority is not None:
            payload["priority"] = record.priority
        with httpx.Client(timeout=15) as client:
            r = client.put(f"{CF_BASE}/zones/{zone_id}/dns_records/{record_id}",
                           json=payload, headers=self._headers)
        data = r.json()
        if data.get("success"):
            return DNSRecordResult(success=True, provider_record_id=record_id)
        err = str(data.get("errors", "unknown"))
        logger.error("Cloudflare update_record failed: %s", err)
        return DNSRecordResult(success=False, error=err)

    def delete_record(self, zone_id: str, record_id: str) -> bool:
        with httpx.Client(timeout=15) as client:
            r = client.delete(f"{CF_BASE}/zones/{zone_id}/dns_records/{record_id}",
                              headers=self._headers)
        return r.json().get("success", False)


class StubDNSAdapter(DNSProviderAdapter):
    """Development stub — no real DNS calls."""

    def create_zone(self, domain_name: str) -> DNSZoneResult:
        logger.info("[STUB dns] create_zone: %s", domain_name)
        return DNSZoneResult(success=True, zone_id=f"stub-zone-{domain_name}")

    def delete_zone(self, zone_id: str) -> bool:
        logger.info("[STUB dns] delete_zone: %s", zone_id)
        return True

    def add_record(self, zone_id: str, record: DNSRecordData) -> DNSRecordResult:
        logger.info("[STUB dns] add_record: %s %s → %s", record.record_type, record.name, record.value)
        return DNSRecordResult(success=True,
                               provider_record_id=f"stub-{record.record_type}-{record.name}")

    def update_record(self, zone_id: str, record_id: str, record: DNSRecordData) -> DNSRecordResult:
        logger.info("[STUB dns] update_record: %s", record_id)
        return DNSRecordResult(success=True, provider_record_id=record_id)

    def delete_record(self, zone_id: str, record_id: str) -> bool:
        logger.info("[STUB dns] delete_record: %s", record_id)
        return True


def get_dns_adapter() -> DNSProviderAdapter:
    if settings.cloudflare_api_token:
        return CloudflareDNSAdapter(settings.cloudflare_api_token, settings.cloudflare_account_id)
    return StubDNSAdapter()
