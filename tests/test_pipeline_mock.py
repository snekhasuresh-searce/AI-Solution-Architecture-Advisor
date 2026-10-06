"""End-to-end run with the mock model (no LLM needed)."""

import os

os.environ["ADVISOR_PROVIDER"] = "mock"

import pytest  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402


async def _run(text: str):
    from advisor.agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name="test")
    session = await runner.session_service.create_session(app_name="test", user_id="t")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    authors = []
    async for ev in runner.run_async(user_id="t", session_id=session.id, new_message=msg):
        authors.append(ev.author)
    session = await runner.session_service.get_session(app_name="test", user_id="t", session_id=session.id)
    return authors, session.state


@pytest.mark.asyncio
async def test_frontend_only_pipeline():
    authors, state = await _run(
        "I need a responsive company website with Home, About and Contact pages. Frontend only."
    )
    assert "cloud_agent" not in authors
    assert "frontend_agent" in authors and "reviewer" in authors
    assert state["domains"] == ["frontend"]


@pytest.mark.asyncio
async def test_vague_request_asks_questions():
    authors, state = await _run("Build me an app.")
    assert "reviewer" not in authors
    assert state["clarification_rounds"] == 1


@pytest.mark.asyncio
async def test_greeting_does_not_run_pipeline():
    authors, state = await _run("hi")
    assert "reviewer" not in authors
    assert not any(a.endswith("_agent") for a in authors)
    assert "clarification_rounds" not in state
