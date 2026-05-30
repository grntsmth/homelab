"""Thin async wrapper around the ServiceNow Table API.

All calls go through a single shared httpx.AsyncClient so connection pooling
and basic-auth setup happen once at app startup.
"""
import logging
from typing import Optional

import httpx

import config

log = logging.getLogger("sn-translator.servicenow")

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        if not config.SN_USER or not config.SN_PASSWORD:
            raise RuntimeError(
                "SN_USER and SN_PASSWORD must be set (injected from sealed secret)"
            )
        _client = httpx.AsyncClient(
            auth=(config.SN_USER, config.SN_PASSWORD),
            timeout=config.SN_HTTP_TIMEOUT,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def create_incident(payload: dict) -> dict:
    """POST /api/now/table/incident — returns the created record."""
    client = get_client()
    resp = await client.post(config.SN_API_BASE, json=payload)
    resp.raise_for_status()
    return resp.json().get("result", {})


async def update_incident(sys_id: str, payload: dict) -> dict:
    """PATCH /api/now/table/incident/{sys_id} — returns the updated record."""
    client = get_client()
    resp = await client.patch(f"{config.SN_API_BASE}/{sys_id}", json=payload)
    resp.raise_for_status()
    return resp.json().get("result", {})


async def ping() -> bool:
    """Cheap readiness check — list one incident to confirm auth works."""
    try:
        client = get_client()
        resp = await client.get(config.SN_API_BASE, params={"sysparm_limit": "1"})
        return resp.status_code == 200
    except Exception as exc:
        log.warning("ServiceNow ping failed: %s", exc)
        return False
