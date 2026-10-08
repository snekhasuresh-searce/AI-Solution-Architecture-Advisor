"""HTTP API used by the React app, end to end on the mock model."""

import json
import os

os.environ["ADVISOR_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from dataclasses import replace

    from advisor import report, storage
    from advisor.api import app

    settings = replace(storage.settings, database_url="", output_dir=str(tmp_path),
                       db_path=str(tmp_path / "runs.sqlite"))
    monkeypatch.setattr(storage, "settings", settings)
    monkeypatch.setattr(report, "settings", settings)
    return TestClient(app)


def _stream(client, session_id, text):
    with client.stream("POST", f"/api/sessions/{session_id}/messages", json={"text": text}) as res:
        assert res.status_code == 200
        return [json.loads(line) for line in res.iter_lines() if line]


def test_run_stream_and_exports(client):
    sid = client.post("/api/sessions").json()["session_id"]
    events = _stream(client, sid, "I need a responsive company website with Home and Contact pages. Frontend only.")
    types = [e["type"] for e in events]
    assert types[0] == "agent_start" and types[-1] == "end" and "error" not in types
    assert next(e for e in events if e["type"] == "plan")["agents"] == ["frontend", "uiux", "security", "performance"]
    assert {"type": "rework", "agents": ["security"]} in events
    assert {"type": "agent_start", "agent": "estimator"} in events
    assert {"type": "agent_done", "agent": "estimator"} in events
    report = next(e for e in events if e["type"] == "report")
    assert report["status"] == "APPROVED" and report["markdown"].startswith("# ")
    for section in ("**Project type:**", "### Recommended architecture", "### Recommended technology stack",
                    "### Required human resources", "### Required AI and technical resources",
                    "### Estimated development effort", "### Estimated timeline"):
        assert section in report["markdown"]

    run_id = report["run_id"]
    assert client.get("/api/runs").json()[0]["run_id"] == run_id
    assert client.get(f"/api/runs/{run_id}/report").json()["markdown"] == report["markdown"]
    for fmt, magic in (("docx", b"PK"), ("pdf", b"%PDF")):
        res = client.get(f"/api/runs/{run_id}/export/{fmt}")
        assert res.status_code == 200 and res.content.startswith(magic)
        assert f"recommendation_{run_id}.{fmt}" in res.headers["content-disposition"]


def test_clarifying_questions_end_without_report(client):
    sid = client.post("/api/sessions").json()["session_id"]
    events = _stream(client, sid, "Build me an app.")
    assert not any(e["type"] in ("plan", "report") for e in events)
    assert any(e["type"] == "message" and "?" in e["text"] for e in events)


def test_bad_requests(client):
    assert client.post("/api/sessions/missing/messages", json={"text": "x"}).status_code == 404
    assert client.get("/api/runs/NOT-A-RUN/export/pdf").status_code == 400
    assert client.get("/api/runs/deadbeef/export/pdf").status_code == 404
    assert client.get("/api/runs/deadbeef/export/html").status_code == 400
    assert client.post("/api/intake", files={"file": ("x.exe", b"MZ")}).status_code == 400
    res = client.post("/api/intake", files={"file": ("req.md", b"# Need\nA REST API")})
    assert res.json() == {"text": "# Need\nA REST API"}
