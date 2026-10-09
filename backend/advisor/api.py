"""HTTP API for the React frontend (../frontend), which is a separate project.

Run (from backend/):  uvicorn advisor.api:app --port 8080 --reload
The web app streams progress from POST /api/sessions/{id}/messages as NDJSON
(one JSON object per line) and downloads exports from /api/runs/{id}/export/{fmt}.
The architecture diagram is served at /api/runs/{id}/diagram.svg and .png.
Browsers may call it from the origins in ADVISOR_CORS_ORIGINS.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from pydantic import BaseModel, Field

from . import architecture, auth, db, diagram, report, storage, tracing
from .agent import build_root_agent
from .auth import User, current_user
from .config import BACKEND_DIR, settings
from .export import EXPORTERS, title_of
from .intake import read_requirement_file
from .models import model_names

log = logging.getLogger("advisor.api")

APP_NAME = "solution_advisor"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

app = FastAPI(title="Nexora — AI solution architecture advisor")


@app.middleware("http")
async def require_client_header(request: Request, call_next):
    """CSRF guard: writes must carry a custom header, which a cross-site form or
    image cannot send, and which cross-origin scripts may only send after CORS
    approves their origin."""
    if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/") \
            and request.headers.get(auth.CLIENT_HEADER) is None:
        return JSONResponse({"detail": f"Missing {auth.CLIENT_HEADER} header"}, status_code=403)
    return await call_next(request)


app.add_middleware(  # added last so it also answers preflights before the check above
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,  # the session cookie
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", auth.CLIENT_HEADER],
    expose_headers=["Content-Disposition"],  # lets the frontend read export file names
)
app.include_router(auth.router)
app.include_router(auth.admin_router)

if settings.auth_mode == "dev":
    log.warning("ADVISOR_AUTH_MODE=dev: anyone can sign in as any %s address. Never use this on a shared server.",
                "/".join(settings.allowed_domains))
elif settings.auth_mode != "google":
    raise RuntimeError(f"ADVISOR_AUTH_MODE must be google or dev, not {settings.auth_mode!r}")

# One agent tree and runner per model provider, built on first use. They share one session database, and
# each session records the provider it was created with, so a conversation stays on its model.
_runners: dict[str, Runner] = {}
SWITCHABLE = ("gemini", "claude")
_KEY_ENV = {"gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "claude": ("ANTHROPIC_API_KEY",)}


def runner(provider: str | None = None) -> Runner:
    """Conversations live in the database (Postgres or SQLite), scoped per user,
    so they survive restarts and work across several API instances."""
    provider = provider or settings.provider
    if provider not in _runners:
        app_ = App(name=APP_NAME, root_agent=build_root_agent(provider), plugins=[tracing.TracingPlugin()])
        _runners[provider] = Runner(app=app_, session_service=DatabaseSessionService(db_url=db.adk_db_url()))
    return _runners[provider]


def _providers() -> list[str]:
    return [*SWITCHABLE, *([settings.provider] if settings.provider not in SWITCHABLE else [])]


def _configured(provider: str) -> bool:
    return provider not in _KEY_ENV or any(os.getenv(k) for k in _KEY_ENV[provider])


class SessionRequest(BaseModel):
    provider: str | None = None


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


def _agent_key(author: str) -> str | None:
    """ADK event author -> the name the web app uses for that agent."""
    if author == "requirement_analyzer":
        return "analyzer"
    if author in ("reviewer", "estimator", "architect"):
        return author
    if author.endswith("_agent"):
        return author.removesuffix("_agent")
    return None


async def _events(user_id: str, session_id: str, text: str, provider: str, usage: dict) -> AsyncIterator[dict]:
    """Translate ADK events into small, UI-friendly progress events."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    yield {"type": "agent_start", "agent": "analyzer"}
    root_name = runner(provider).agent.name
    async for event in runner(provider).run_async(user_id=user_id, session_id=session_id, new_message=message):
        delta = (event.actions.state_delta if event.actions else None) or {}
        meta = None if event.partial else event.usage_metadata
        if meta:
            usage["input"] += meta.prompt_token_count or 0
            usage["output"] += meta.candidates_token_count or 0
            yield {"type": "usage", "provider": provider, **usage}
        if event.author != root_name:
            agent = _agent_key(event.author)
            if agent and (f"spec_{agent}" in delta or {"analysis", "review", "estimate", "architecture"} & delta.keys()):
                yield {"type": "agent_done", "agent": agent}
            continue
        if "selected_agents" in delta:
            yield {"type": "plan", "agents": delta["selected_agents"]}
        if "estimate_context" in delta:
            yield {"type": "agent_start", "agent": "estimator"}
        rework = [k.removeprefix("rework_") for k, v in delta.items() if k.startswith("rework_") and v]
        if rework:
            yield {"type": "rework", "agents": rework}
        if "architect_context" in delta:
            yield {"type": "agent_start", "agent": "architect"}
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
            "database": "postgres" if settings.database_url else "sqlite", "auth": settings.auth_mode}


@app.get("/api/models")
def models(_: User = Depends(current_user)) -> dict:
    """Providers the web app can switch between, and which one new sessions use by default."""
    return {"default": settings.provider,
            "providers": [{"id": p, "models": model_names(p), "configured": _configured(p)} for p in _providers()]}


@app.get("/api/model-usage")
def model_usage(_: User = Depends(current_user)) -> dict:
    """Tokens used this month per provider, against the optional budget (GEMINI_TOKEN_BUDGET / CLAUDE_TOKEN_BUDGET)."""
    used = storage.usage_this_month()
    budgets = {"gemini": settings.gemini_token_budget, "claude": settings.claude_token_budget}
    out = {}
    for p in _providers():
        i, o = used.get(p, (0, 0))
        budget = budgets.get(p, 0) or None
        out[p] = {"input": i, "output": o, "total": i + o, "budget": budget,
                  "remaining": max(budget - i - o, 0) if budget else None}
    return {"period": "month", "providers": out}


@app.get("/api/scenarios")
def scenarios(_: User = Depends(current_user)) -> list[dict]:
    return [{"name": p.stem.split("_", 1)[-1].replace("_", " ").title(), "text": p.read_text().strip()}
            for p in sorted((BACKEND_DIR / "scenarios").glob("*.txt"))]


@app.post("/api/sessions")
async def create_session(body: SessionRequest | None = None, user: User = Depends(current_user)) -> dict:
    provider = (body.provider if body else None) or settings.provider
    if provider not in _providers():
        raise HTTPException(400, f"Unknown model provider {provider!r}; use one of {', '.join(_providers())}")
    if not _configured(provider):
        raise HTTPException(400, f"No API key set for {provider}. Add {_KEY_ENV[provider][0]} to .env and restart the API.")
    session = await runner(provider).session_service.create_session(
        app_name=APP_NAME, user_id=user.id, state={"provider": provider})
    return {"session_id": session.id, "provider": provider}


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, body: Message, user: User = Depends(current_user)) -> StreamingResponse:
    # Sessions are looked up under the caller's id, so nobody can continue someone else's.
    session = await runner().session_service.get_session(app_name=APP_NAME, user_id=user.id, session_id=session_id)
    if session is None:
        raise HTTPException(404, "Session not found. Start a new requirement.")
    provider = session.state.get("provider") or settings.provider  # sessions from before the model switch

    async def stream() -> AsyncIterator[str]:
        used = {"input": 0, "output": 0}
        try:
            async for item in _events(user.id, session_id, body.text.strip(), provider, used):
                yield json.dumps(item) + "\n"
        except Exception as exc:  # noqa: BLE001 - report to the browser instead of cutting the stream
            log.exception("Advisor run failed")
            yield json.dumps({"type": "error", "message": f"{type(exc).__name__}: {exc}"}) + "\n"
        finally:
            storage.log_usage(provider, used["input"], used["output"])  # also counts a failed or aborted run
        yield json.dumps({"type": "end"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/intake")
async def intake(file: UploadFile, _: User = Depends(current_user)) -> dict:
    """Extract requirement text from an uploaded .txt / .md / .pdf / .docx."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise HTTPException(400, "Upload a .txt, .md, .pdf or .docx file.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    # Closed before reading: Windows cannot reopen a NamedTemporaryFile that is still open.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
    try:
        text = read_requirement_file(tmp.name)
    except Exception as exc:  # noqa: BLE001 - corrupt or unreadable document
        raise HTTPException(400, f"Could not read {file.filename}: {exc}") from exc
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return {"text": text.strip()}


@app.get("/api/runs")
def runs(limit: int = 30, mine: bool = False, user: User = Depends(current_user)) -> list[dict]:
    """Consultants see their own runs; reviewers and admins see everyone's (or only theirs with mine=true)."""
    owner = None if user.can_see_all_runs() and not mine else user.id
    rows = storage.recent_runs(min(limit, 100), owner_id=owner)
    owners = storage.run_owners([r[0] for r in rows]) if owner is None else {r[0]: user.id for r in rows}
    emails = auth.emails_by_id({o for o in owners.values() if o})
    metrics = tracing.run_summaries([r[0] for r in rows])
    out = []
    for run_id, created, domains, agents, status, overall, rounds in rows:
        try:
            markdown = report.load(run_id)
        except ValueError:
            markdown = None
        out.append({"run_id": run_id, "created_at": created, "domains": [d for d in domains.split(",") if d],
                    "agents": [a for a in agents.split(",") if a], "status": status, "overall": overall,
                    "rounds": rounds, "title": title_of(markdown) if markdown else None,
                    "has_report": markdown is not None, "owner": emails.get(owners.get(run_id) or ""),
                    **metrics.get(run_id, {"duration_ms": None, "tokens": None, "cost_usd": None})})
    return out


def check_run_access(run_id: str, user: User = Depends(current_user)) -> str:
    """Owner, reviewer or admin. Others get 404 so they cannot probe which run ids exist."""
    try:
        report.path_for(run_id)  # validates the id format
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not user.can_see_all_runs() and storage.run_owners([run_id]).get(run_id) != user.id:
        raise HTTPException(404, f"No report for run {run_id}")
    return run_id


def _report_or_404(run_id: str) -> str:
    try:
        markdown = report.load(run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if markdown is None:
        raise HTTPException(404, f"No report for run {run_id}")
    return markdown


@app.get("/api/runs/{run_id}/report")
def run_report(run_id: str = Depends(check_run_access)) -> dict:
    return {"run_id": run_id, "markdown": _report_or_404(run_id)}


@app.get("/api/runs/{run_id}/export/{fmt}")
def export(fmt: str, run_id: str = Depends(check_run_access)) -> Response:
    if fmt not in EXPORTERS:
        raise HTTPException(400, f"Unknown format {fmt!r}; use one of {', '.join(EXPORTERS)}")
    render, media_type = EXPORTERS[fmt]
    markdown = _report_or_404(run_id)
    content = render(markdown, architecture.load(run_id))
    filename = f"recommendation_{run_id}.{fmt}"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/runs/{run_id}/architecture")
def run_architecture(run_id: str = Depends(check_run_access)) -> dict:
    return _architecture_or_404(run_id)


def _architecture_or_404(run_id: str) -> dict:
    try:
        arch = architecture.load(run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if arch is None:
        raise HTTPException(404, f"No architecture for run {run_id}")
    return arch


@app.get("/api/runs/{run_id}/diagram.{fmt}")
def run_diagram(fmt: str, download: bool = False, run_id: str = Depends(check_run_access)) -> Response:
    if fmt not in ("svg", "png"):
        raise HTTPException(400, "Use diagram.svg or diagram.png")
    arch = _architecture_or_404(run_id)
    content, media_type = ((diagram.to_svg(arch).encode(), "image/svg+xml") if fmt == "svg"
                           else (diagram.to_png(arch), "image/png"))
    headers = {"Content-Disposition": f'attachment; filename="architecture_{run_id}.{fmt}"'} if download else {}
    return Response(content, media_type=media_type, headers=headers)



@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str = Depends(check_run_access)) -> dict:
    """Every turn, agent and model call behind a run, with time, tokens and cost."""
    spans = tracing.run_trace(run_id)
    if not spans:
        raise HTTPException(404, f"No trace for run {run_id} (runs from before tracing have none)")
    return {"run_id": run_id, "spans": spans}


@app.get("/api/usage")
def usage(days: int = 30, _: User = Depends(auth.require_roles("reviewer", "admin"))) -> dict:
    """Totals and outliers across all users, for reviewers and admins."""
    data = tracing.usage(max(1, min(days, 365)))
    emails = auth.emails_by_id({u["key"] for u in data["by_user"] if u["key"]}
                               | {r["user_id"] for r in data["slowest"] + data["most_expensive"] if r["user_id"]})
    for u in data["by_user"]:
        u["email"] = emails.get(u["key"], u["key"])
    for r in data["slowest"] + data["most_expensive"]:
        r["email"] = emails.get(r["user_id"], r["user_id"])
    return data
