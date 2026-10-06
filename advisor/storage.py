"""Run log in a local SQLite file (stands in for Firestore in the POC)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    session_id  TEXT,
    created_at  TEXT,
    requirement TEXT,
    domains     TEXT,
    agents      TEXT,
    status      TEXT,
    overall     REAL,
    rounds      INTEGER,
    payload     TEXT
);
"""


def _connect() -> sqlite3.Connection:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(_SCHEMA)
    return conn


def log_run(*, run_id, session_id, requirement, domains, agents, status, overall, rounds, payload) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, session_id, datetime.now(timezone.utc).isoformat(), requirement,
             ",".join(domains), ",".join(agents), status, overall, rounds, json.dumps(payload, default=str)),
        )


def recent_runs(limit: int = 20) -> list[tuple]:
    with _connect() as conn:
        return conn.execute(
            "SELECT run_id, created_at, domains, agents, status, overall, rounds FROM runs "
            "ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
