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
    payload     TEXT,
    owner_id    TEXT
);
"""

_SQLITE_USAGE = """
CREATE TABLE IF NOT EXISTS usage (
    created_at    TEXT,
    provider      TEXT,
    input_tokens  INTEGER,
    output_tokens INTEGER
);
"""

_PG_USAGE = """
CREATE TABLE IF NOT EXISTS usage (
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    provider      TEXT,
    input_tokens  BIGINT,
    output_tokens BIGINT
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
-- Added with sign-in: the user who ran it (users.id). Older runs have none.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS owner_id TEXT;
CREATE INDEX IF NOT EXISTS runs_owner_idx ON runs (owner_id, created_at DESC);
"""


def _use_postgres() -> bool:
    return bool(settings.database_url)


# ------------------------------------------------------------------ SQLite
def _sqlite() -> sqlite3.Connection:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(_SQLITE_SCHEMA)
    conn.execute(_SQLITE_USAGE)
    if "owner_id" not in {c[1] for c in conn.execute("PRAGMA table_info(runs)")}:  # log from before sign-in
        conn.execute("ALTER TABLE runs ADD COLUMN owner_id TEXT")
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
            conn.execute(_PG_USAGE)
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


def _log_run(*, postgres, run_id, session_id, requirement, domains, agents, status, overall, rounds, payload,
             owner_id=None) -> None:
    body = json.dumps(payload, default=str)
    if postgres:
        with _postgres() as conn:
            conn.execute(
                """INSERT INTO runs (run_id, session_id, requirement, domains, agents, status, overall, rounds, payload,
                                    owner_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                   ON CONFLICT (run_id) DO UPDATE SET
                     session_id = EXCLUDED.session_id, requirement = EXCLUDED.requirement,
                     domains = EXCLUDED.domains, agents = EXCLUDED.agents, status = EXCLUDED.status,
                     overall = EXCLUDED.overall, rounds = EXCLUDED.rounds, payload = EXCLUDED.payload,
                     owner_id = EXCLUDED.owner_id""",
                (run_id, session_id, requirement, list(domains), list(agents), status, overall, rounds, body,
                 owner_id),
            )
        return
    with _sqlite() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, session_id, created_at, requirement, domains, agents, status, "
            "overall, rounds, payload, owner_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, session_id, datetime.now(timezone.utc).isoformat(), requirement,
             ",".join(domains), ",".join(agents), status, overall, rounds, body, owner_id),
        )


def recent_runs(limit: int = 20, owner_id: str | None = None) -> list[tuple]:
    """(run_id, created_at ISO text, domains, agents, status, overall, rounds), newest first.
    With owner_id, only that user's runs."""
    cols = "SELECT run_id, created_at, domains, agents, status, overall, rounds FROM runs"
    if _use_postgres():
        where, args = (" WHERE owner_id = %s", (owner_id, limit)) if owner_id else ("", (limit,))
        with _postgres() as conn:
            rows = conn.execute(f"{cols}{where} ORDER BY created_at DESC LIMIT %s", args).fetchall()
        return [(r[0], r[1].isoformat(), ",".join(r[2] or []), ",".join(r[3] or []), *r[4:]) for r in rows]
    where, args = (" WHERE owner_id = ?", (owner_id, limit)) if owner_id else ("", (limit,))
    with _sqlite() as conn:
        return conn.execute(f"{cols}{where} ORDER BY created_at DESC LIMIT ?", args).fetchall()


def run_owners(run_ids: list[str]) -> dict[str, str | None]:
    """run_id -> owner_id for the given runs (missing runs are left out)."""
    if not run_ids:
        return {}
    if _use_postgres():
        with _postgres() as conn:
            rows = conn.execute("SELECT run_id, owner_id FROM runs WHERE run_id = ANY(%s)", (run_ids,)).fetchall()
    else:
        marks = ",".join("?" * len(run_ids))
        with _sqlite() as conn:
            rows = conn.execute(f"SELECT run_id, owner_id FROM runs WHERE run_id IN ({marks})", run_ids).fetchall()
    return dict(rows)


# ------------------------------------------------------------- token usage
def log_usage(provider: str, input_tokens: int, output_tokens: int) -> None:
    """Record the tokens one advisor run used. Never raises: usage tracking must not fail a run."""
    if not (input_tokens or output_tokens):
        return
    try:
        if _use_postgres():
            with _postgres() as conn:
                conn.execute("INSERT INTO usage (provider, input_tokens, output_tokens) VALUES (%s, %s, %s)",
                             (provider, input_tokens, output_tokens))
            return
        with _sqlite() as conn:
            conn.execute("INSERT INTO usage VALUES (?,?,?,?)",
                         (datetime.now(timezone.utc).isoformat(), provider, input_tokens, output_tokens))
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not record token usage (%s: %s)", type(exc).__name__, exc)


def usage_this_month() -> dict[str, tuple[int, int]]:
    """provider -> (input_tokens, output_tokens) used since the start of the current UTC month."""
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if _use_postgres():
        with _postgres() as conn:
            rows = conn.execute("SELECT provider, SUM(input_tokens), SUM(output_tokens) FROM usage "
                                "WHERE created_at >= %s GROUP BY provider", (start,)).fetchall()
    else:
        with _sqlite() as conn:  # ISO timestamps sort as text
            rows = conn.execute("SELECT provider, SUM(input_tokens), SUM(output_tokens) FROM usage "
                                "WHERE created_at >= ? GROUP BY provider", (start.isoformat(),)).fetchall()
    return {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}
