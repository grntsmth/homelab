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


class InstanceHibernatingError(RuntimeError):
    """A PDI answered with its HTML hibernation page instead of the API.

    Personal Developer Instances hibernate after ~10 idle days and answer
    every request with HTTP 200 + an HTML wake page — so neither status
    codes nor raise_for_status() catch it. Waking requires a login at
    developer.servicenow.com; API calls cannot do it.
    """


def _parse_result(resp: httpx.Response) -> dict:
    resp.raise_for_status()
    if "application/json" not in resp.headers.get("content-type", ""):
        raise InstanceHibernatingError(
            f"ServiceNow returned non-JSON ({resp.headers.get('content-type', 'unknown')}, "
            f"status {resp.status_code}) — the PDI is likely hibernating. "
            "Wake it via developer.servicenow.com; Alertmanager will re-deliver."
        )
    return resp.json().get("result", {})


async def create_incident(payload: dict) -> dict:
    """POST /api/now/table/incident — returns the created record."""
    client = get_client()
    resp = await client.post(config.SN_API_BASE, json=payload)
    return _parse_result(resp)


async def update_incident(sys_id: str, payload: dict) -> dict:
    """PATCH /api/now/table/incident/{sys_id} — returns the updated record."""
    client = get_client()
    resp = await client.patch(f"{config.SN_API_BASE}/{sys_id}", json=payload)
    return _parse_result(resp)


async def ping() -> bool:
    """Cheap readiness check — list one incident to confirm auth works.

    A hibernating PDI answers 200 with HTML, which is NOT reachable for
    our purposes — /health must not report ok when creates would fail.
    """
    try:
        client = get_client()
        resp = await client.get(config.SN_API_BASE, params={"sysparm_limit": "1"})
        return (
            resp.status_code == 200
            and "application/json" in resp.headers.get("content-type", "")
        )
    except Exception as exc:
        log.warning("ServiceNow ping failed: %s", exc)
        return False
