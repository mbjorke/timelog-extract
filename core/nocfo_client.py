"""Minimal NoCFO REST client: create a sales-invoice DRAFT, nothing else.

Gittan proposes, the user approves, NoCFO does the accounting. This client
therefore exposes exactly one write — ``POST /v1/invoicing/{business}/invoice/``,
which NoCFO creates in ``DRAFT`` status — plus a read used to verify the token.
It deliberately has **no** accept, send, mark-paid or delete call: a human
accepts and sends the invoice inside NoCFO.

Endpoint shapes follow NoCFO's own open-source toolkit (``nocfo-cli`` on PyPI)
and the request schemas in NoCFO's published OpenAPI document:
base ``https://api-prd.nocfo.io``, header ``Authorization: Token <token>``, a
personal token created at login.nocfo.io. Credentials come from the
environment (``NOCFO_API_TOKEN``, ``NOCFO_BUSINESS``, optional
``NOCFO_BASE_URL``) — the same variable names ``nocfo-cli`` reads — or from CLI
flags. Tokens are never written to disk by Gittan.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

from core.http_security import build_https_opener

DEFAULT_BASE_URL = "https://api-prd.nocfo.io"
ENV_TOKEN = "NOCFO_API_TOKEN"
ENV_BUSINESS = "NOCFO_BUSINESS"
ENV_BASE_URL = "NOCFO_BASE_URL"
_TIMEOUT_SECONDS = 20


class NocfoHttpError(RuntimeError):
    """NoCFO answered with an HTTP error: the request definitely did not succeed."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class NocfoCredentials:
    api_token: str
    business: str  # NoCFO business slug, as used in API paths
    base_url: str = DEFAULT_BASE_URL

    def __repr__(self) -> str:  # never leak the token into logs/tracebacks
        return f"NocfoCredentials(business={self.business!r}, base_url={self.base_url!r})"


def resolve_nocfo_credentials(
    token: Optional[str] = None,
    business: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[NocfoCredentials]:
    """Flags win over environment; ``None`` when token or business is missing."""
    resolved_token = (token or os.environ.get(ENV_TOKEN) or "").strip()
    resolved_business = (business or os.environ.get(ENV_BUSINESS) or "").strip()
    resolved_base = (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip("/")
    if not resolved_token or not resolved_business:
        return None
    return NocfoCredentials(resolved_token, resolved_business, resolved_base)


def draft_invoice_path(business: str) -> str:
    return f"/v1/invoicing/{quote(business, safe='')}/invoice/"


def _request(creds: NocfoCredentials, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        f"{creds.base_url}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Token {creds.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "gittan-nocfo-draft",
        },
    )
    opener = build_https_opener("NoCFO")
    try:
        with opener.open(req, timeout=_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8") or "null"
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:  # noqa: BLE001 - best-effort error detail
            pass
        raise NocfoHttpError(f"NoCFO {method} {path} failed: HTTP {exc.code} {detail}".strip(), exc.code) from None
    except URLError as exc:
        raise RuntimeError(f"NoCFO {method} {path} failed: {exc.reason}") from None
    return json.loads(raw)


def verify_business_access(creds: NocfoCredentials) -> Dict[str, Any]:
    """Read the business record; raises if the token cannot see this business."""
    parsed = _request(creds, "GET", f"/v1/business/{quote(creds.business, safe='')}/")
    if not isinstance(parsed, dict):
        raise RuntimeError("NoCFO returned an unexpected response for the business lookup")
    return parsed


def get_product(creds: NocfoCredentials, product_id: int) -> Dict[str, Any]:
    """Read one invoicing product (name, unit, price, VAT) — read-only."""
    path = f"/v1/invoicing/{quote(creds.business, safe='')}/product/{int(product_id)}/"
    parsed = _request(creds, "GET", path)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"NoCFO returned an unexpected response for product {product_id}")
    return parsed


def create_draft_invoice(creds: NocfoCredentials, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create one sales invoice in DRAFT status and return NoCFO's response.

    Refuses a payload that tries to set a status: drafts only.
    """
    if "status" in payload:
        raise ValueError("Gittan only creates NoCFO drafts; payload must not set 'status'")
    parsed = _request(creds, "POST", draft_invoice_path(creds.business), payload)
    if not isinstance(parsed, dict) or parsed.get("id") in (None, ""):
        raise RuntimeError("NoCFO response missing invoice id")
    return parsed
