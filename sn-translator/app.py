"""FastAPI entrypoint — translates Alertmanager webhooks into ServiceNow incidents."""
import logging
from contextlib import asynccontextmanager
from time import monotonic

import httpx
from fastapi import FastAPI, HTTPException

import config
import models
import servicenow
from translator import alert_to_incident_payload, resolve_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("sn-translator")

# Cache the SN reachability check between /health probes. Without this, a
# 15s readinessProbe interval translates to ~240 SN auth attempts per hour
# per replica, which both wastes PDI quota and trips account lockouts on
# password mismatch. The cache TTL is intentionally short — fresh enough
# that a real SN outage surfaces within a minute, slow enough that a
# probe storm can't lock the account.
_HEALTH_CACHE_TTL_SECONDS = 60.0
_health_cache = {"checked_at": 0.0, "reachable": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.init_db()
    log.info("sn-translator started: SN_INSTANCE=%s db=%s", config.SN_INSTANCE, config.DB_PATH)
    yield
    await servicenow.close_client()
    log.info("sn-translator shutting down")


app = FastAPI(title="sn-translator", lifespan=lifespan)


async def _create_for_alert(alert: models.Alert) -> dict:
    existing = models.lookup_incident(alert.fingerprint)
    if existing and not existing.get("resolved_at"):
        log.info(
            "Alert %s already mapped to %s — skipping duplicate create",
            alert.fingerprint, existing["number"],
        )
        return {"action": "skipped", "reason": "duplicate", "incident": existing}

    payload = alert_to_incident_payload(alert)
    try:
        created = await servicenow.create_incident(payload)
    except httpx.HTTPStatusError as exc:
        log.error("SN create failed: %s %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail=f"ServiceNow create failed: {exc}")

    sys_id = created.get("sys_id", "")
    number = created.get("number", "")
    models.remember_incident(alert.fingerprint, sys_id, number, alert.labels.get("alertname", ""))
    log.info("Created incident %s (%s) for alert %s", number, sys_id, alert.fingerprint)
    return {"action": "created", "incident": {"sys_id": sys_id, "number": number}}


async def _resolve_for_alert(alert: models.Alert) -> dict:
    existing = models.lookup_incident(alert.fingerprint)
    if not existing:
        log.warning("Resolve for unknown fingerprint %s — nothing to close", alert.fingerprint)
        return {"action": "skipped", "reason": "unknown_fingerprint"}
    if existing.get("resolved_at"):
        return {"action": "skipped", "reason": "already_resolved", "incident": existing}

    close_notes = f"Auto-resolved by Alertmanager (fingerprint {alert.fingerprint})."
    if alert.endsAt:
        close_notes += f" endsAt={alert.endsAt}"

    try:
        updated = await servicenow.update_incident(existing["sys_id"], resolve_payload(close_notes))
    except httpx.HTTPStatusError as exc:
        log.error("SN resolve failed: %s %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail=f"ServiceNow update failed: {exc}")

    models.mark_resolved(alert.fingerprint)
    log.info("Resolved incident %s for alert %s", existing["number"], alert.fingerprint)
    return {"action": "resolved", "incident": {"sys_id": existing["sys_id"], "number": existing["number"]}, "result": updated}


@app.post("/webhook")
async def webhook(payload: models.AlertmanagerPayload):
    """Receive an Alertmanager webhook; dispatch firing → create, resolved → close.

    Alertmanager sends both firing and resolved alerts to the same webhook when
    `send_resolved: true` is set, with a per-alert `status` field. We honour
    that here so a single route handles the full lifecycle.
    """
    results = []
    for alert in payload.alerts:
        if alert.status == "firing":
            results.append(await _create_for_alert(alert))
        elif alert.status == "resolved":
            results.append(await _resolve_for_alert(alert))
        else:
            log.warning("Unknown alert status %r — ignoring", alert.status)
            results.append({"action": "skipped", "reason": f"unknown_status:{alert.status}"})
    return {"processed": len(results), "results": results}


@app.post("/resolve")
async def resolve(payload: models.AlertmanagerPayload):
    """Explicit resolved-only endpoint.

    Useful when Alertmanager routes resolved alerts to a separate receiver, or
    for manual closure during a runbook. Ignores firing alerts so a misrouted
    payload can't accidentally re-open incidents.
    """
    results = []
    for alert in payload.alerts:
        if alert.status != "resolved":
            results.append({"action": "skipped", "reason": "not_resolved", "fingerprint": alert.fingerprint})
            continue
        results.append(await _resolve_for_alert(alert))
    return {"processed": len(results), "results": results}


@app.get("/health")
async def health():
    """Liveness + cached ServiceNow reachability check."""
    now = monotonic()
    age = now - _health_cache["checked_at"]
    if age > _HEALTH_CACHE_TTL_SECONDS:
        _health_cache["reachable"] = await servicenow.ping()
        _health_cache["checked_at"] = now
        age = 0.0
    return {
        "status": "ok",
        "servicenow_reachable": _health_cache["reachable"],
        "servicenow_check_age_seconds": round(age, 1),
        "instance": config.SN_INSTANCE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
