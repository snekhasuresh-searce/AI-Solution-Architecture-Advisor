"""HTTP API used by the React app, end to end on the mock model."""

import json
import os

os.environ["ADVISOR_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from dataclasses import replace

    from advisor import architecture, report, storage
    from advisor.api import app

    settings = replace(storage.settings, database_url="", output_dir=str(tmp_path),
                       db_path=str(tmp_path / "runs.sqlite"))
    monkeypatch.setattr(storage, "settings", settings)
    monkeypatch.setattr(report, "settings", settings)
    monkeypatch.setattr(architecture, "settings", settings)
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

    # Architecture stage: progress event, report section and diagram endpoints.
    assert {"type": "agent_done", "agent": "architect"} in events
    assert f"/api/runs/{run_id}/diagram.svg" in report["markdown"]
    svg = client.get(f"/api/runs/{run_id}/diagram.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    png = client.get(f"/api/runs/{run_id}/diagram.png?download=true")
    assert png.content[1:4] == b"PNG" and "attachment" in png.headers["content-disposition"]
    assert client.get(f"/api/runs/{run_id}/architecture").json()["nodes"]
    assert client.get(f"/api/runs/{run_id}/diagram.gif").status_code == 400


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


def test_models_and_session_provider(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    listed = client.get("/api/models").json()
    assert listed["default"] == "mock"
    assert [p["id"] for p in listed["providers"]] == ["gemini", "claude", "mock"]
    assert next(p for p in listed["providers"] if p["id"] == "claude")["configured"] is False
    # Switching to a provider without a key is refused with a pointer to the setting.
    res = client.post("/api/sessions", json={"provider": "claude"})
    assert res.status_code == 400 and "ANTHROPIC_API_KEY" in res.json()["detail"]
    assert client.post("/api/sessions", json={"provider": "nope"}).status_code == 400
    assert client.post("/api/sessions", json={"provider": "mock"}).json()["provider"] == "mock"


def test_usage_budget_and_remaining(client, monkeypatch):
    from dataclasses import replace

    from advisor import api, storage

    monkeypatch.setattr(api, "settings", replace(api.settings, claude_token_budget=1000))
    storage.log_usage("claude", 300, 150)
    storage.log_usage("claude", 50, 0)
    claude = client.get("/api/usage").json()["providers"]["claude"]
    assert (claude["input"], claude["output"], claude["total"]) == (350, 150, 500)
    assert claude["budget"] == 1000 and claude["remaining"] == 500
    gemini = client.get("/api/usage").json()["providers"]["gemini"]
    assert gemini["budget"] is None and gemini["remaining"] is None
