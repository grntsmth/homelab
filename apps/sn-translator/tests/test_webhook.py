"""Batch-handling tests for the /webhook endpoint.

The invariant under test: one poisoned alert must never abort the rest of
the batch, and any failure must surface as a 502 so Alertmanager retries
(creates are fingerprint-deduplicated, so retries are safe).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

import app as app_module
import models
import servicenow
from app import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "incidents.db"), raising=False)
    import config

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "incidents.db"))
    models.init_db()
    yield


def make_alert(fingerprint: str, status: str = "firing", alertname: str = "TestAlert") -> dict:
    return {
        "status": status,
        "labels": {"alertname": alertname, "severity": "warning"},
        "annotations": {"summary": f"{alertname} fired"},
        "startsAt": "2026-07-12T00:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
        "generatorURL": "http://prometheus/graph",
        "fingerprint": fingerprint,
    }


def payload(*alerts: dict) -> dict:
    return {
        "version": "4",
        "groupKey": "{}:{}",
        "status": "firing",
        "receiver": "servicenow",
        "alerts": list(alerts),
    }


def test_poisoned_alert_does_not_abort_batch(monkeypatch):
    """Alert 1 fails at ServiceNow; alerts 2 and 3 must still be processed."""
    calls = []

    async def fake_create(p):
        calls.append(p["short_description"])
        if len(calls) == 1:
            raise servicenow.InstanceHibernatingError("hibernating")
        return {"sys_id": f"sys-{len(calls)}", "number": f"INC{len(calls)}"}

    monkeypatch.setattr(servicenow, "create_incident", fake_create)

    with TestClient(app) as client:
        resp = client.post(
            "/webhook",
            json=payload(make_alert("f1", alertname="A1"), make_alert("f2", alertname="A2"),
                         make_alert("f3", alertname="A3")),
        )

    assert len(calls) == 3, "later alerts in the batch were never attempted"
    body = resp.json()
    assert body["processed"] == 3
    actions = [r["action"] for r in body["results"]]
    assert actions == ["error", "created", "created"]
    # any failure -> 502 so Alertmanager retries the group
    assert resp.status_code == 502


def test_all_success_returns_200(monkeypatch):
    async def fake_create(p):
        return {"sys_id": "sys-1", "number": "INC1"}

    monkeypatch.setattr(servicenow, "create_incident", fake_create)

    with TestClient(app) as client:
        resp = client.post("/webhook", json=payload(make_alert("f1")))

    assert resp.status_code == 200
    assert resp.json()["results"][0]["action"] == "created"


def test_duplicate_firing_is_skipped_on_retry(monkeypatch):
    """Simulates the Alertmanager retry after a partial failure."""
    created = []

    async def fake_create(p):
        created.append(p)
        return {"sys_id": "sys-1", "number": "INC1"}

    monkeypatch.setattr(servicenow, "create_incident", fake_create)

    with TestClient(app) as client:
        first = client.post("/webhook", json=payload(make_alert("dup-1")))
        second = client.post("/webhook", json=payload(make_alert("dup-1")))

    assert first.json()["results"][0]["action"] == "created"
    assert second.json()["results"][0]["action"] == "skipped"
    assert len(created) == 1, "retry must not create a second incident"


def test_resolve_unknown_fingerprint_is_skip_not_error():
    with TestClient(app) as client:
        resp = client.post("/webhook", json=payload(make_alert("ghost", status="resolved")))

    assert resp.status_code == 200
    assert resp.json()["results"][0]["reason"] == "unknown_fingerprint"
