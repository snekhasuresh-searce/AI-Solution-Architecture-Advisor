"""HTTP API for the React web app (web/).

Run:  uvicorn advisor.api:app --port 8080 --reload
The web app streams progress from POST /api/sessions/{id}/messages as NDJSON
(one JSON object per line) and downloads exports from /api/runs/{id}/export/{fmt}.
If web/dist exists (npm run build), it is served at / as well.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from . import report, storage
from .agent import root_agent
from .config import settings
from .export import EXPORTERS, title_of
from .intake import read_requirement_file

log = logging.getLogger("advisor.api")

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "solution_advisor"
USER_ID = "web"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="AI Solution Architecture Advisor")
runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


def _agent_key(author: str) -> str | None:
    """ADK event author -> the name the web app uses for that agent."""
    if author == "requirement_analyzer":
        return "analyzer"
    if author in ("reviewer", "estimator"):
        return author
    if author.endswith("_agent"):
        return author.removesuffix("_agent")
    return None


async def _events(session_id: str, text: str) -> AsyncIterator[dict]:
    """Translate ADK events into small, UI-friendly progress events."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    yield {"type": "agent_start", "agent": "analyzer"}
    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=message):
        delta = (event.actions.state_delta if event.actions else None) or {}
        if event.author != root_agent.name:
            agent = _agent_key(event.author)
            if agent and (f"spec_{agent}" in delta or {"analysis", "review", "estimate"} & delta.keys()):
                yield {"type": "agent_done", "agent": agent}
            continue
        if "selected_agents" in delta:
            yield {"type": "plan", "agents": delta["selected_agents"]}
        if "estimate_context" in delta:
            yield {"type": "agent_start", "agent": "estimator"}
        rework = [k.removeprefix("rework_") for k, v in delta.items() if k.startswith("rework_") and v]
        if rework:
            yield {"type": "rework", "agents": rework}
        if "last_run" in delta:
            run = delta["last_run"]
            yield {"type": "report", "run_id": run["run_id"], "status": run["status"],
                   "markdown": report.load(run["run_id"]) or ""}
            continue
        text_out = "".join(p.text or "" for p in (event.content.parts if event.content else []) if p.text)
        if text_out:
            yield {"type": "message", "text": text_out}


# --------------------------------------------------------------------- API
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.provider,
            "database": "postgres" if settings.database_url else "sqlite"}


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return [{"name": p.stem.split("_", 1)[-1].replace("_", " ").title(), "text": p.read_text().strip()}
            for p in sorted((ROOT / "scenarios").glob("*.txt"))]


@app.post("/api/sessions")
async def create_session() -> dict:
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    return {"session_id": session.id}


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, body: Message) -> StreamingResponse:
    session = await runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    if session is None:
        raise HTTPException(404, "Session not found (the server may have restarted). Start a new requirement.")

    async def stream() -> AsyncIterator[str]:
        try:
            async for item in _events(session_id, body.text.strip()):
                yield json.dumps(item) + "\n"
        except Exception as exc:  # noqa: BLE001 - report to the browser instead of cutting the stream
            log.exception("Advisor run failed")
            yield json.dumps({"type": "error", "message": f"{type(exc).__name__}: {exc}"}) + "\n"
        yield json.dumps({"type": "end"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/intake")
async def intake(file: UploadFile) -> dict:
    """Extract requirement text from an uploaded .txt / .md / .pdf / .docx."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise HTTPException(400, "Upload a .txt, .md, .pdf or .docx file.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            text = read_requirement_file(tmp.name)
        except Exception as exc:  # noqa: BLE001 - corrupt or unreadable document
            raise HTTPException(400, f"Could not read {file.filename}: {exc}") from exc
    return {"text": text.strip()}


@app.get("/api/runs")
def runs(limit: int = 30) -> list[dict]:
    out = []
    for run_id, created, domains, agents, status, overall, rounds in storage.recent_runs(min(limit, 100)):
        try:
            markdown = report.load(run_id)
        except ValueError:
            markdown = None
        out.append({"run_id": run_id, "created_at": created, "domains": [d for d in domains.split(",") if d],
                    "agents": [a for a in agents.split(",") if a], "status": status, "overall": overall,
                    "rounds": rounds, "title": title_of(markdown) if markdown else None,
                    "has_report": markdown is not None})
    return out


def _report_or_404(run_id: str) -> str:
    try:
        markdown = report.load(run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if markdown is None:
        raise HTTPException(404, f"No report for run {run_id}")
    return markdown


@app.get("/api/runs/{run_id}/report")
def run_report(run_id: str) -> dict:
    return {"run_id": run_id, "markdown": _report_or_404(run_id)}


@app.get("/api/runs/{run_id}/export/{fmt}")
def export(run_id: str, fmt: str) -> Response:
    if fmt not in EXPORTERS:
        raise HTTPException(400, f"Unknown format {fmt!r}; use one of {', '.join(EXPORTERS)}")
    render, media_type = EXPORTERS[fmt]
    content = render(_report_or_404(run_id))
    filename = f"recommendation_{run_id}.{fmt}"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# Production: serve the built web app from the same origin.
_DIST = ROOT / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
