"""Run log on SQLite (always) and Postgres (when ADVISOR_TEST_DATABASE_URL is set)."""

import os
import uuid
from dataclasses import replace

import pytest

from advisor import storage

PG_URL = os.getenv("ADVISOR_TEST_DATABASE_URL", "")


def _roundtrip():
    run_id = f"test_{uuid.uuid4().hex[:8]}"
    storage.log_run(run_id=run_id, session_id="s", requirement="A website", domains=["frontend"],
                    agents=["frontend", "security"], status="APPROVED", overall=91.5, rounds=1,
                    payload={"brief": {"title": "Site"}})
    # Logging again with the same id updates the row instead of failing.
    storage.log_run(run_id=run_id, session_id="s", requirement="A website", domains=["frontend"],
                    agents=["frontend", "security"], status="ESCALATED", overall=70.0, rounds=4, payload={})
    row = next(r for r in storage.recent_runs(50) if r[0] == run_id)
    assert row[2:] == ("frontend", "frontend,security", "ESCALATED", 70.0, 4)
    assert row[1][:4].isdigit()  # ISO timestamp text, as scripts/list_runs.py expects
    return run_id


def test_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "settings", replace(storage.settings, database_url="",
                                                     db_path=str(tmp_path / "runs.sqlite")))
    _roundtrip()


@pytest.mark.skipif(not PG_URL, reason="set ADVISOR_TEST_DATABASE_URL to test Postgres")
def test_postgres(monkeypatch):
    import psycopg

    monkeypatch.setattr(storage, "settings", replace(storage.settings, database_url=PG_URL))
    monkeypatch.setattr(storage, "_pg_ready", False)
    run_id = _roundtrip()
    with psycopg.connect(PG_URL) as conn:
        assert conn.execute("SELECT payload->>'brief' FROM runs WHERE run_id = %s", (run_id,)).fetchone() == (None,)
        conn.execute("DELETE FROM runs WHERE run_id = %s", (run_id,))


def test_postgres_failure_falls_back_to_sqlite(tmp_path, monkeypatch, caplog):
    path = tmp_path / "runs.sqlite"
    monkeypatch.setattr(storage, "settings", replace(storage.settings, db_path=str(path),
                                                     database_url="postgresql://nobody@127.0.0.1:1/none"))
    monkeypatch.setattr(storage, "_pg_ready", False)
    storage.log_run(run_id="fallback", session_id="s", requirement="r", domains=["frontend"], agents=["frontend"],
                    status="APPROVED", overall=90.0, rounds=1, payload={})
    assert "logged to SQLite" in caplog.text
    monkeypatch.setattr(storage, "settings", replace(storage.settings, database_url=""))
    assert storage.recent_runs()[0][0] == "fallback"
