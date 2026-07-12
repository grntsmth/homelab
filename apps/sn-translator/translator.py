"""Alertmanager Alert → ServiceNow incident field translation.

Kept separate from the HTTP / SQLite layers so the mapping logic is
easy to unit-test in isolation.
"""
from typing import Optional

import config
from models import Alert


def map_namespace_to_category(namespace: Optional[str]) -> str:
    """Translate a Kubernetes namespace into a ServiceNow category choice.

    Stock PDIs reject "infrastructure" silently — see
    config.NAMESPACE_TO_CATEGORY for the full quirks list.
    """
    if not namespace:
        return "inquiry"
    return config.NAMESPACE_TO_CATEGORY.get(namespace.lower(), "inquiry")


def map_severity_to_urgency(severity: Optional[str]) -> int:
    if not severity:
        return 3
    return config.SEVERITY_TO_URGENCY.get(severity.lower(), 3)


def alert_to_incident_payload(alert: Alert) -> dict:
    """Build the JSON body for POST /api/now/table/incident."""
    labels = alert.labels
    annotations = alert.annotations

    alertname = labels.get("alertname", "Unknown alert")
    severity = labels.get("severity", "info")
    namespace = labels.get("namespace")
    instance = labels.get("instance", "")
    # Chaos rules label their alerts chaos_signal; accept the older
    # chaos_type spellings too so a stale rule set still enriches.
    chaos_type = (
        labels.get("chaos_signal")
        or labels.get("chaos_type")
        or labels.get("chaos-type")
    )

    short_description = annotations.get("summary") or alertname
    description_body = annotations.get("description", "")

    # Stitch a few extra labels into the description body so the on-call
    # engineer can see the alert context without leaving ServiceNow.
    description_lines = [description_body] if description_body else []
    description_lines.append("")
    description_lines.append(f"Alertname: {alertname}")
    description_lines.append(f"Severity: {severity}")
    if namespace:
        description_lines.append(f"Namespace: {namespace}")
    if instance:
        description_lines.append(f"Instance: {instance}")
    if chaos_type:
        description_lines.append(f"Chaos type: {chaos_type}")
    if alert.generatorURL:
        description_lines.append(f"Source: {alert.generatorURL}")
    if alert.fingerprint:
        description_lines.append(f"Fingerprint: {alert.fingerprint}")

    urgency = map_severity_to_urgency(severity)

    payload = {
        "short_description": short_description[:160],  # SN soft cap
        "description": "\n".join(description_lines).strip(),
        "urgency": urgency,
        "impact": urgency,  # mirror urgency unless we add a separate signal
        "category": map_namespace_to_category(namespace),
        # caller_id is load-bearing for the resolve path: SN's incident
        # workflow refuses state transitions on incidents with an empty
        # caller. Discovered when manually closing an orphan test incident
        # returned 403. Always set it, even when we don't have a "real"
        # caller — the API user is a sensible fallback.
        "caller_id": config.SN_USER,
    }

    # cmdb_ci is a reference field in real ServiceNow; on a PDI we can pass a
    # display value and the platform will store it as a string (no CI lookup).
    if instance:
        payload["cmdb_ci"] = instance

    return payload


def resolve_payload(close_notes: str) -> dict:
    """Patch body that closes a ServiceNow incident."""
    return {
        "state": config.SN_STATE_RESOLVED,
        "incident_state": config.SN_STATE_RESOLVED,
        # SN's incident workflow may rewrite this to "Resolved by caller"
        # depending on the resolver/caller relationship — observed during
        # smoke testing. Keep the explicit value here for intent; the actual
        # stored value is whatever SN's business rules decide.
        "close_code": "Solved (Permanently)",
        "close_notes": close_notes,
        "resolved_by": config.SN_USER,
    }
