"""Run log: PostgreSQL when ADVISOR_DATABASE_URL is set, else a local SQLite file.

SQLite keeps the quick start dependency-free; Postgres is for shared or
long-lived logs (e.g. Cloud SQL). Both expose the same two functions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

log = logging.getLogger("advisor.storage")

_SQLITE_SCHEMA = """
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

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    session_id  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    requirement TEXT,
    domains     TEXT[],
    agents      TEXT[],
    status      TEXT,
    overall     DOUBLE PRECISION,
    rounds      INTEGER,
    payload     JSONB
);
CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at DESC);
"""


def _use_postgres() -> bool:
    return bool(settings.database_url)


# ------------------------------------------------------------------ SQLite
def _sqlite() -> sqlite3.Connection:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(_SQLITE_SCHEMA)
    return conn


# ---------------------------------------------------------------- Postgres
_pg_ready = False


def _postgres():
    import psycopg  # only needed when Postgres is configured

    global _pg_ready
    conn = psycopg.connect(settings.database_url)
    if not _pg_ready:
        with conn.transaction():
            conn.execute(_PG_SCHEMA)
        _pg_ready = True
    return conn


# -------------------------------------------------------------------- API
def log_run(**run) -> None:
    """Log a run. A Postgres failure (driver missing, server down) must not lose
    the finished recommendation, so it falls back to SQLite with a warning."""
    if _use_postgres():
        try:
            _log_run(postgres=True, **run)
            return
        except Exception as exc:  # noqa: BLE001 - any failure here is non-fatal
            log.warning("Postgres run log failed (%s: %s); logged to SQLite at %s instead.",
                        type(exc).__name__, exc, settings.db_path)
    _log_run(postgres=False, **run)


def _log_run(*, postgres, run_id, session_id, requirement, domains, agents, status, overall, rounds, payload) -> None:
    body = json.dumps(payload, default=str)
    if postgres:
        with _postgres() as conn:
            conn.execute(
                """INSERT INTO runs (run_id, session_id, requirement, domains, agents, status, overall, rounds, payload)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (run_id) DO UPDATE SET
                     session_id = EXCLUDED.session_id, requirement = EXCLUDED.requirement,
                     domains = EXCLUDED.domains, agents = EXCLUDED.agents, status = EXCLUDED.status,
                     overall = EXCLUDED.overall, rounds = EXCLUDED.rounds, payload = EXCLUDED.payload""",
                (run_id, session_id, requirement, list(domains), list(agents), status, overall, rounds, body),
            )
        return
    with _sqlite() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, session_id, datetime.now(timezone.utc).isoformat(), requirement,
             ",".join(domains), ",".join(agents), status, overall, rounds, body),
        )


def recent_runs(limit: int = 20) -> list[tuple]:
    """(run_id, created_at ISO text, domains, agents, status, overall, rounds), newest first."""
    if _use_postgres():
        with _postgres() as conn:
            rows = conn.execute(
                "SELECT run_id, created_at, domains, agents, status, overall, rounds FROM runs "
                "ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return [(r[0], r[1].isoformat(), ",".join(r[2] or []), ",".join(r[3] or []), *r[4:]) for r in rows]
    with _sqlite() as conn:
        return conn.execute(
            "SELECT run_id, created_at, domains, agents, status, overall, rounds FROM runs "
            "ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
