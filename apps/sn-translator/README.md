# sn-translator

FastAPI service that translates Alertmanager webhook payloads into
ServiceNow incidents and closes them on resolution.

Deployment manifests live in [`manifests/`](manifests/). The full
pipeline architecture is documented in [`../../chaos/README.md`](../../chaos/README.md).

## Endpoints

| Method | Path        | Purpose |
|--------|-------------|---------|
| POST   | `/webhook`  | Receive any Alertmanager payload; dispatch firing → create incident, resolved → close incident. |
| POST   | `/resolve`  | Resolved-only endpoint. Firing alerts in the payload are skipped — safety hatch for misrouted webhooks. |
| GET    | `/health`   | Liveness + ServiceNow reachability probe. |

## Layout

| File              | Responsibility |
|-------------------|----------------|
| `app.py`          | FastAPI app, lifespan, route handlers. |
| `config.py`       | Env-var loading, severity/namespace mapping tables, SN state constants. |
| `models.py`       | Pydantic models for Alertmanager schema + SQLite fingerprint store. |
| `servicenow.py`   | Thin async wrapper around the Table API (`httpx.AsyncClient`). |
| `translator.py`   | Pure functions: `Alert` → SN incident payload, resolved payload. |

The split mirrors Chronicle's pattern so the two services age the same
way.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export SN_INSTANCE=devXXXXXX.service-now.com   # your PDI hostname
export SN_USER='<your PDI API user>'
export SN_PASSWORD='<your PDI password>'

uvicorn app:app --reload --port 8091
```

Smoke-test with a synthetic Alertmanager payload:

```bash
curl -X POST http://localhost:8091/webhook \
  -H 'content-type: application/json' \
  -d '{
    "version": "4",
    "status": "firing",
    "receiver": "servicenow",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical",
        "team": "infrastructure",
        "namespace": "ecosystem",
        "instance": "high-palace"
      },
      "annotations": {
        "summary": "Synthetic test from curl",
        "description": "If you see this incident in your PDI the pipeline is wired."
      },
      "fingerprint": "test-fingerprint-001"
    }]
  }'
```

## Tests

```bash
pip install -r requirements-dev.txt
ruff check . && pytest
```

The suite covers the mapping logic (`translator.py`) and the webhook
batch semantics — most importantly that one poisoned alert cannot abort
the rest of an Alertmanager group, and that any failure returns 502 so
Alertmanager retries against the fingerprint-deduplicated store.

## Image build

```bash
docker build -t sn-translator:latest .
docker save sn-translator:latest -o /tmp/sn.tar
sudo /usr/local/bin/k3s ctr images import /tmp/sn.tar && rm /tmp/sn.tar
kubectl -n ecosystem rollout restart deploy/sn-translator
```

(`imagePullPolicy: IfNotPresent` — the image never leaves the node.)
