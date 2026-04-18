"""
.ax Registry adapter.

The StubRegistryAdapter logs all calls and returns synthetic data — useful
for local development without real registry credentials.

To plug in the actual .ax registry:
1. Subclass RegistryAdapter
2. Implement check_availability / register / delete using EPP or their REST API
3. Swap the returned adapter in get_registry_adapter()
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class RegistrationRequest:
    domain_name: str
    registrant_name: str
    registrant_email: str
    registrant_org: Optional[str]
    registrant_country: str
    nameserver1: str
    nameserver2: str
    years: int = 1


@dataclass
class RegistrationResult:
    success: bool
    registry_reference: Optional[str]
    expires_at: Optional[datetime]
    error: Optional[str] = None


class RegistryAdapter(ABC):
    @abstractmethod
    def check_availability(self, domain_name: str) -> bool:
        pass

    @abstractmethod
    def register(self, request: RegistrationRequest) -> RegistrationResult:
        pass

    @abstractmethod
    def delete(self, registry_reference: str) -> bool:
        pass


class StubRegistryAdapter(RegistryAdapter):
    """Development stub — replace with real .ax registry integration."""

    def check_availability(self, domain_name: str) -> bool:
        logger.info("[STUB registry] check_availability: %s", domain_name)
        return True

    def register(self, request: RegistrationRequest) -> RegistrationResult:
        logger.info("[STUB registry] register: %s (ns: %s, %s)",
                    request.domain_name, request.nameserver1, request.nameserver2)
        slug = request.domain_name.upper().replace(".", "-")
        ref = f"AX-{slug}-{datetime.utcnow().strftime('%Y%m%d')}"
        expires = datetime.utcnow() + timedelta(days=365 * request.years)
        return RegistrationResult(success=True, registry_reference=ref, expires_at=expires)

    def delete(self, registry_reference: str) -> bool:
        logger.info("[STUB registry] delete: %s", registry_reference)
        return True


def get_registry_adapter() -> RegistryAdapter:
    if settings.registry_api_key:
        logger.warning(
            "registry_api_key is set but no real adapter is wired up — "
            "falling back to StubRegistryAdapter. Implement AxRegistryAdapter."
        )
    return StubRegistryAdapter()
