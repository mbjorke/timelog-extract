#!/usr/bin/env python3
"""
Standalone Briox API connection test.

Uses environment variables:
  BRIOX_AUTH_TOKEN
  BRIOX_USER_EMAIL
  BRIOX_APPLICATION_ID
  BRIOX_COMPANY_ID
Optional:
  BRIOX_API_BASE
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
DEFAULT_BRIOX_API_BASE = "https://api-se.briox.services/v2"
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


def extract_access_token(payload):
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        direct = data.get("access_token")
        if direct:
            return direct
        nested = data.get("accesstoken", {})
        if isinstance(nested, dict):
            return nested.get("access_token")
    return None


def require_env():
    auth_token = os.getenv("BRIOX_AUTH_TOKEN", "").strip()
    user_email = os.getenv("BRIOX_USER_EMAIL", "").strip()
    application_id = os.getenv("BRIOX_APPLICATION_ID", "").strip()
    company_id = os.getenv("BRIOX_COMPANY_ID", "").strip()
    missing = [
        key
        for key, value in {
            "BRIOX_AUTH_TOKEN": auth_token,
            "BRIOX_USER_EMAIL": user_email,
            "BRIOX_APPLICATION_ID": application_id,
            "BRIOX_COMPANY_ID": company_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing Briox env vars: " + ", ".join(missing))
    return auth_token, user_email, application_id, company_id


def get_access_token(auth_token, user_email, application_id, company_id):
    token_body = {
        "accesstokendata": {
            "user_email": user_email,
            "application_id": application_id,
            "company_id": company_id,
        }
    }
    token_headers = [{"Authorization": auth_token}, {"Authorization": f"Bearer {auth_token}"}]
    configured_api_base = os.getenv("BRIOX_API_BASE", "").strip().rstrip("/")
    api_bases = [configured_api_base] if configured_api_base else BRIOX_API_BASE_CANDIDATES
    if not api_bases:
        api_bases = [DEFAULT_BRIOX_API_BASE]

    attempts = []
    for api_base in api_bases:
        query = urlencode({"clientid": company_id, "token": auth_token})
        status, payload = http_json("POST", f"{api_base}/token?{query}", body=None, headers={})
        attempts.append(
            {"api_base": api_base, "method": "POST /token", "status": status, "payload": payload}
        )
        if status < 400:
            token = extract_access_token(payload)
            if token:
                return api_base, token, payload

        token_url = f"{api_base}/clientaccesstoken"
        for hdr in token_headers:
            status, payload = http_json("POST", token_url, body=token_body, headers=hdr)
            attempts.append(
                {
                    "api_base": api_base,
                    "method": "POST /clientaccesstoken",
                    "header": hdr["Authorization"][:18] + "...",
                    "status": status,
                    "payload": payload,
                }
            )
            if status < 400:
                token = extract_access_token(payload)
                if token:
                    return api_base, token, payload

    raise RuntimeError(f"Token request failed. Attempts: {attempts}")


def main():
    args = parse_args()
    auth_token, user_email, application_id, company_id = require_env()
    api_base, access_token, token_payload = get_access_token(
        auth_token, user_email, application_id, company_id
    )

    if args.token_only:
        data = token_payload.get("data", {}) if isinstance(token_payload, dict) else {}
        print("Briox token test OK")
        print(f"  API base: {api_base}")
        if data.get("client_id") is not None:
            print(f"  Client ID: {data.get('client_id')}")
        if data.get("expire_date"):
            print(f"  Valid until: {data.get('expire_date')}")
        print(f"  Access token prefix: {access_token[:8]}...")
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
        },
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
