"""Runtime configuration for sn-translator.

Everything is sourced from environment variables; the SealedSecret in
k8s/sn-translator/sealed-secret.yml supplies the ServiceNow credentials at
runtime so nothing sensitive ever lives in this repo.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# --- ServiceNow PDI ---
SN_INSTANCE = os.getenv("SN_INSTANCE", "devXXXXXX.service-now.com")
SN_USER = os.getenv("SN_USER", "")
SN_PASSWORD = os.getenv("SN_PASSWORD", "")
SN_API_BASE = f"https://{SN_INSTANCE}/api/now/table/incident"
SN_HTTP_TIMEOUT = float(os.getenv("SN_HTTP_TIMEOUT", "10.0"))

# --- Service ---
PORT = int(os.getenv("SN_TRANSLATOR_PORT", "8091"))
DB_PATH = os.getenv("SN_TRANSLATOR_DB", str(BASE_DIR / "data" / "incidents.db"))

# --- Field mapping quirks ---
#
# devXXXXXX (Personal Developer Instance) ships with a stock category choice
# list that does NOT include "infrastructure". The closest equivalent that
# the PDI accepts without ACL errors is "inquiry". Anything else we don't
# explicitly map gets passed through verbatim and ServiceNow will reject
# unknown choices silently by storing an empty value, so we'd rather
# normalise here than discover that on the dashboard.
NAMESPACE_TO_CATEGORY = {
    "infrastructure": "inquiry",
    "monitoring": "inquiry",
    "kube-system": "inquiry",
    "ecosystem": "software",
    "chaos-mesh": "inquiry",
    "minecraft": "software",
}

# Alertmanager severity → ServiceNow urgency/impact.
# SN scale: 1 = High, 2 = Medium, 3 = Low.
SEVERITY_TO_URGENCY = {
    "critical": 1,
    "warning": 2,
    "info": 3,
}

# ServiceNow incident_state values
SN_STATE_NEW = 1
SN_STATE_IN_PROGRESS = 2
SN_STATE_RESOLVED = 6
SN_STATE_CLOSED = 7
