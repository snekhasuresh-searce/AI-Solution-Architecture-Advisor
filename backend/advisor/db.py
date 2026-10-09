"""Database connections for the app's own tables and for ADK sessions.

Postgres when ADVISOR_DATABASE_URL is set, else the local SQLite file at
ADVISOR_DB_PATH. The same database holds the run log, users and login
sessions, and ADK's conversation tables (sessions, events, ...).
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, event

from .config import settings


def _postgres_url(driver: str) -> str:
    url = settings.database_url
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return f"postgresql+{driver}://" + url[len(prefix):]
    return url  # already names a driver


def app_db_url() -> str:
    """Synchronous URL for the app's tables (users, auth_sessions, ...)."""
    return _postgres_url("psycopg") if settings.database_url else f"sqlite:///{settings.db_path}"


def adk_db_url() -> str:
    """Async URL for ADK's DatabaseSessionService."""
    return _postgres_url("asyncpg") if settings.database_url else f"sqlite+aiosqlite:///{settings.db_path}"


@lru_cache(maxsize=1)
def engine() -> Engine:
    url = app_db_url()
    if url.startswith("sqlite"):
        from pathlib import Path

        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        eng = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(eng, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        return eng
    return create_engine(url, pool_pre_ping=True)
