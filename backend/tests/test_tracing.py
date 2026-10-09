"""Traces, token use and cost per run, and who may see them."""

import json
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from advisor import mock_llm, tracing
from advisor.api import app
from advisor.pricing import cost_usd, price

HEADERS = {"X-Advisor-Client": "test"}
WEBSITE = "I need a responsive company website with Home and Contact pages. Frontend only."


def signed_in(role: str | None = None) -> TestClient:
    client = TestClient(app, headers=HEADERS)
    body = {"email": f"trace-{uuid.uuid4().hex[:6]}@searce.com", **({"role": role} if role else {})}
    assert client.post("/api/auth/dev-login", json=body).status_code == 200
    return client


def run(client: TestClient, *texts: str) -> str:
    sid = client.post("/api/sessions").json()["session_id"]
    for text in texts:
        with client.stream("POST", f"/api/sessions/{sid}/messages", json={"text": text}) as res:
            events = [json.loads(line) for line in res.iter_lines() if line]
    return next(e for e in events if e["type"] == "report")["run_id"]


# ------------------------------------------------------------- pricing
def test_prices_follow_the_dated_table():
    assert price("gemini-3.8-flash", date(2026, 12, 31))["input"] == 0.75
    assert price("gemini-3.8-flash", date(2027, 1, 1))["input"] == 1.50  # announced increase
    assert price("models/gemini-3.5-flash-lite")["output"] == 2.50
    assert price("mock-strong") == {"input": 0.0, "output": 0.0, "cached_input": 0.0}
    assert price("ollama_chat/qwen2.5:14b")["input"] == 0.0
    assert price("some-unknown-model") is None


def test_cost_counts_cache_and_thinking_correctly():
    # 10k input of which 2k cached, 1.5k output + 0.5k thinking (billed as output).
    assert cost_usd("gemini-3.5-flash-lite", input_tokens=10_000, cached_tokens=2_000, output_tokens=1_500,
                    thinking_tokens=500) == pytest.approx((8_000 * 0.30 + 2_000 * 0.03 + 2_000 * 2.50) / 1e6)
    assert cost_usd("claude-opus-5-5", input_tokens=1_000_000, cached_tokens=0, output_tokens=0,
                    thinking_tokens=0) == 4.0
    assert cost_usd("unknown", input_tokens=1, cached_tokens=0, output_tokens=1, thinking_tokens=0) is None


# -------------------------------------------------------------- traces
def test_trace_covers_every_turn_agent_and_model_call():
    client = signed_in()
    run_id = run(client, "Build me an app.", WEBSITE + " Use your assumptions.")
    spans = client.get(f"/api/runs/{run_id}/trace").json()["spans"]

    turns = [s for s in spans if s["kind"] == "run"]
    assert len(turns) == 2  # the clarifying-question turn counts toward the run
    agents = [s for s in spans if s["kind"] == "agent"]
    calls = [s for s in spans if s["kind"] == "llm"]
    assert {"requirement_analyzer", "frontend_agent", "reviewer", "estimator"} <= {s["name"] for s in agents}
    assert all(c["model"].startswith("mock-") and c["input_tokens"] > 0 for c in calls)
    # The mock reviewer asks security for one rework: second attempts are recorded.
    assert any(s["name"] == "security_agent" and s["attempt"] == 2 for s in agents)
    assert any(s["name"] == "reviewer" and s["attempt"] == 2 for s in agents)
    # Totals roll up: the turn spans add up their model calls.
    assert sum(t["input_tokens"] for t in turns) == sum(c["input_tokens"] for c in calls)
    orchestrator = next(s for s in agents if s["name"] == "solution_advisor" and s["input_tokens"])
    assert orchestrator["input_tokens"] == sum(c["input_tokens"] for c in calls
                                               if c["trace_id"] == orchestrator["trace_id"])

    listed = next(r for r in client.get("/api/runs").json() if r["run_id"] == run_id)
    assert listed["cost_usd"] == 0.0 and listed["tokens"] > 0 and listed["duration_ms"] >= 0


def test_failed_model_call_is_recorded(monkeypatch):
    original = mock_llm.MockLlm.generate_content_async

    async def flaky(self, llm_request, stream=False):
        if "ROLE: estimator" in mock_llm._system_text(llm_request):
            raise RuntimeError("model overloaded (503)")
        async for response in original(self, llm_request, stream):
            yield response

    monkeypatch.setattr(mock_llm.MockLlm, "generate_content_async", flaky)
    client = signed_in()
    run_id = run(client, WEBSITE)  # the orchestrator still delivers a report without an estimate
    spans = client.get(f"/api/runs/{run_id}/trace").json()["spans"]
    failed = [s for s in spans if s["status"] == "error"]
    assert any(s["kind"] == "llm" and s["name"] == "estimator" and "overloaded" in s["error"] for s in failed)


# --------------------------------------------------------------- access
def test_trace_and_usage_access():
    owner, other, reviewer = signed_in(), signed_in(), signed_in("reviewer")
    run_id = run(owner, WEBSITE)
    assert other.get(f"/api/runs/{run_id}/trace").status_code == 404
    assert reviewer.get(f"/api/runs/{run_id}/trace").status_code == 200
    assert owner.get("/api/usage").status_code == 403

    data = reviewer.get("/api/usage?days=7").json()
    assert data["totals"]["count"] >= 1 and data["totals"]["tokens"] > 0
    assert any(m["key"].startswith("mock-") for m in data["by_model"])
    assert {"requirement_analyzer", "reviewer"} <= {a["key"] for a in data["by_agent"]}
    assert any(u["email"].startswith("trace-") for u in data["by_user"])
    assert data["slowest"] and data["most_expensive"]
