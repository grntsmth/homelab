"""Pydantic models for Alertmanager webhook payloads + SQLite mapping store.

Alertmanager webhook schema reference:
https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

import config


class Alert(BaseModel):
    status: str  # "firing" | "resolved"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: str  # Alertmanager-stable per-alert identifier


class AlertmanagerPayload(BaseModel):
    """Outer envelope Alertmanager POSTs to a webhook receiver."""
    version: str = "4"
    groupKey: Optional[str] = None
    status: str  # group-level status
    receiver: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: list[Alert]


def init_db() -> None:
    """Create the incidents table if it doesn't already exist."""
    db = Path(config.DB_PATH)
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                fingerprint TEXT PRIMARY KEY,
                sys_id TEXT NOT NULL,
                number TEXT NOT NULL,
                alertname TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                resolved_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_sys_id ON incidents(sys_id)"
        )


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def remember_incident(fingerprint: str, sys_id: str, number: str, alertname: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO incidents (fingerprint, sys_id, number, alertname) "
            "VALUES (?, ?, ?, ?)",
            (fingerprint, sys_id, number, alertname),
        )


def lookup_incident(fingerprint: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT fingerprint, sys_id, number, alertname, created_at, resolved_at "
            "FROM incidents WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
    return dict(row) if row else None


def mark_resolved(fingerprint: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE incidents SET resolved_at = datetime('now') WHERE fingerprint = ?",
            (fingerprint,),
        )
