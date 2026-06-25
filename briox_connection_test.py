#!/usr/bin/env python3
"""
Standalone Briox API connection test (Finnish environment).

Primary flow (Blueberry Maybe integration — not Briox Connect):
  POST {BRIOX_API_BASE}/token?clientid={BRIOX_COMPANY_ID}&token={BRIOX_AUTH_TOKEN}
  → access_token + refresh_token (30-day access; refresh via POST /tokenrefresh)

Required environment variables:
  BRIOX_AUTH_TOKEN   Application Token from Admin → Users → Application Token,
                     integration **Blueberry Maybe** (not Briox Connect)
  BRIOX_COMPANY_ID   Briox account ID (clientid), e.g. 35826158

Optional:
  BRIOX_API_BASE     default https://api-fi.briox.services/v2
  BRIOX_ACCESS_TOKEN Skip /token if you already have a valid access token
  BRIOX_REFRESH_TOKEN Required with BRIOX_ACCESS_TOKEN for --refresh-only
  BRIOX_USER_EMAIL   Only for legacy POST /clientaccesstoken fallback
  BRIOX_APPLICATION_ID
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlencode

SCRIPT_DIR = Path(__file__).parent
DEFAULT_BRIOX_API_BASE = "https://api-fi.briox.services/v2"
BRIOX_API_BASE_CANDIDATES = [
    "https://api-fi.briox.services/v2",
    "https://api-se.briox.services/v2",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Test Briox API connection and token flow")
    parser.add_argument(
        "--invoice-limit",
        type=int,
        default=10,
        help="Number of customer invoices to fetch (default: 10)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to save full JSON snapshot",
    )
    parser.add_argument(
        "--token-only",
        action="store_true",
        help="Only validate token flow (skip company and invoice calls)",
    )
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Only call POST /tokenrefresh using BRIOX_ACCESS_TOKEN + BRIOX_REFRESH_TOKEN",
    )
    return parser.parse_args()


def http_json(method, url, body=None, headers=None, timeout=20):
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = {"Accept": "application/json"}
    if encoded is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = urlrequest.Request(url, data=encoded, method=method, headers=req_headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urlerror.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        payload = {}
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw}
        return exc.code, payload


def _token_fields(payload):
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return None, None
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if access:
        return access, refresh
    nested = data.get("accesstoken", {})
    if isinstance(nested, dict):
        return nested.get("access_token"), nested.get("refresh_token")
    return None, None


def require_env_token_exchange():
    auth_token = os.getenv("BRIOX_AUTH_TOKEN", "").strip()
    company_id = os.getenv("BRIOX_COMPANY_ID", "").strip()
    missing = [
        key
        for key, value in {
            "BRIOX_AUTH_TOKEN": auth_token,
            "BRIOX_COMPANY_ID": company_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing Briox env vars: " + ", ".join(missing))
    return auth_token, company_id


def require_env_refresh():
    access = os.getenv("BRIOX_ACCESS_TOKEN", "").strip()
    refresh = os.getenv("BRIOX_REFRESH_TOKEN", "").strip()
    missing = [
        key
        for key, value in {
            "BRIOX_ACCESS_TOKEN": access,
            "BRIOX_REFRESH_TOKEN": refresh,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing Briox env vars for refresh: " + ", ".join(missing))
    return access, refresh


def api_bases():
    configured = os.getenv("BRIOX_API_BASE", "").strip().rstrip("/")
    if configured:
        return [configured]
    return list(BRIOX_API_BASE_CANDIDATES)


def exchange_application_token(auth_token, company_id):
    """POST /token?clientid=&token= — Blueberry Maybe Application Token."""
    attempts = []
    for api_base in api_bases():
        query = urlencode({"clientid": company_id, "token": auth_token})
        status, payload = http_json("POST", f"{api_base}/token?{query}", body=None, headers={})
        attempts.append(
            {"api_base": api_base, "method": "POST /token", "status": status, "payload": payload}
        )
        if status < 400:
            access, refresh = _token_fields(payload)
            if access:
                return api_base, access, refresh, payload
    raise RuntimeError(f"POST /token failed. Attempts: {attempts}")


def refresh_access_token(api_base, access_token, refresh_token):
    attempts = []
    body = {
        "accesstokendata": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    }
    for hdr in [{"Authorization": access_token}, {"Authorization": f"Bearer {access_token}"}]:
        status, payload = http_json(
            "POST",
            f"{api_base}/tokenrefresh",
            body=body,
            headers=hdr,
        )
        attempts.append(
            {
                "api_base": api_base,
                "method": "POST /tokenrefresh",
                "status": status,
                "payload": payload,
            }
        )
        if status < 400:
            access, refresh = _token_fields(payload)
            if access:
                return access, refresh, payload
    raise RuntimeError(f"POST /tokenrefresh failed. Attempts: {attempts}")


def legacy_client_access_token(auth_token, user_email, application_id, company_id):
    """Fallback if Briox enables /clientaccesstoken for this integration."""
    token_body = {
        "accesstokendata": {
            "user_email": user_email,
            "application_id": application_id,
            "company_id": company_id,
        }
    }
    token_headers = [{"Authorization": auth_token}, {"Authorization": f"Bearer {auth_token}"}]
    attempts = []
    for api_base in api_bases():
        token_url = f"{api_base}/clientaccesstoken"
        for hdr in token_headers:
            status, payload = http_json("POST", token_url, body=token_body, headers=hdr)
            attempts.append(
                {
                    "api_base": api_base,
                    "method": "POST /clientaccesstoken",
                    "status": status,
                    "payload": payload,
                }
            )
            if status < 400:
                access, refresh = _token_fields(payload)
                if access:
                    return api_base, access, refresh, payload
    raise RuntimeError(f"Legacy /clientaccesstoken failed. Attempts: {attempts}")


def get_access_token(auth_token, company_id):
    try:
        return exchange_application_token(auth_token, company_id)
    except RuntimeError as primary_err:
        user_email = os.getenv("BRIOX_USER_EMAIL", "").strip()
        application_id = os.getenv("BRIOX_APPLICATION_ID", "").strip()
        if user_email and application_id:
            api_base, access, refresh, payload = legacy_client_access_token(
                auth_token, user_email, application_id, company_id
            )
            return api_base, access, refresh, payload
        raise primary_err


def resolve_access_token(auth_token, company_id):
    preset = os.getenv("BRIOX_ACCESS_TOKEN", "").strip()
    if preset:
        api_base = api_bases()[0]
        refresh = os.getenv("BRIOX_REFRESH_TOKEN", "").strip() or None
        return api_base, preset, refresh, {"data": {"access_token": preset, "refresh_token": refresh}}

    return get_access_token(auth_token, company_id)


def print_token_summary(api_base, access_token, refresh_token, token_payload):
    data = token_payload.get("data", {}) if isinstance(token_payload, dict) else {}
    print("Briox token OK")
    print(f"  API base: {api_base}")
    if isinstance(data, dict):
        if data.get("client_id") is not None:
            print(f"  Client ID: {data.get('client_id')}")
        if data.get("expire_date"):
            print(f"  Valid until: {data.get('expire_date')}")
    print(f"  Access token prefix: {access_token[:8]}...")
    if refresh_token:
        print(f"  Refresh token prefix: {refresh_token[:8]}...")
        print("  Save both tokens locally — each refresh returns a new pair.")


def main():
    args = parse_args()
    api_base = api_bases()[0]

    if args.refresh_only:
        access_token, refresh_token = require_env_refresh()
        access_token, refresh_token, token_payload = refresh_access_token(
            api_base, access_token, refresh_token
        )
        print_token_summary(api_base, access_token, refresh_token, token_payload)
        return

    auth_token, company_id = require_env_token_exchange()
    api_base, access_token, refresh_token, token_payload = resolve_access_token(auth_token, company_id)

    if args.token_only:
        print_token_summary(api_base, access_token, refresh_token, token_payload)
        return

    auth_headers = [
        {"Authorization": access_token},
        {"Authorization": f"Bearer {access_token}"},
    ]

    company_status = None
    company_payload = None
    invoice_status = None
    invoice_payload = None
    for hdr in auth_headers:
        company_status, company_payload = http_json("GET", f"{api_base}/company/info", headers=hdr)
        if company_status < 400:
            invoice_status, invoice_payload = http_json(
                "GET",
                f"{api_base}/customerinvoice?limit={max(args.invoice_limit, 1)}",
                headers=hdr,
            )
            if invoice_status < 400:
                break

    if company_status is None or company_status >= 400:
        raise RuntimeError(f"Failed /company/info: {company_status} {company_payload}")
    if invoice_status is None or invoice_status >= 400:
        raise RuntimeError(f"Failed /customerinvoice: {invoice_status} {invoice_payload}")

    invoices = invoice_payload.get("data", {}).get("invoices", [])
    company = company_payload.get("data", {}).get("company", {})
    company_name = company.get("name") or company.get("company_name") or "<unknown>"

    snapshot = {
        "meta": {
            "api_base": api_base,
            "company_id": company_id,
            "fetched_at": datetime.now().isoformat(),
            "invoice_limit": args.invoice_limit,
            "access_token_prefix": access_token[:8],
            "refresh_token_prefix": (refresh_token or "")[:8] if refresh_token else None,
        },
        "token_exchange": token_payload,
        "company_info": company_payload,
        "customer_invoices": invoice_payload,
    }
    if args.output_json:
        out_path = Path(args.output_json).expanduser()
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = SCRIPT_DIR / "output" / "briox" / f"briox-test-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Briox API test OK")
    print(f"  API base: {api_base}")
    print(f"  Company: {company_name}")
    print(f"  Invoices fetched: {len(invoices)}")
    print(f"  Snapshot saved: {out_path}")


if __name__ == "__main__":
    main()
