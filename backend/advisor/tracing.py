"""Traces per run: a span tree of run -> agents -> model calls, with timing,
tokens, cost and errors, stored in the database and written to the logs.

The ADK plugin below sees every agent and model call. Each run is buffered in
memory and saved in one transaction when it ends (or fails), so tracing adds
no database round trips while the agents work.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, func, insert, select

from . import db
from .logs import event
from .pricing import cost_usd

log = logging.getLogger("advisor.trace")

metadata = MetaData()
trace_spans = Table(
    "trace_spans", metadata,
    Column("id", String(32), primary_key=True),
    Column("trace_id", String(64), nullable=False, index=True),  # ADK invocation id: one user turn
    Column("run_id", String(16), index=True),                    # the recommendation it produced, if any
    Column("session_id", String(64), index=True),
    Column("user_id", String(64), index=True),
    Column("parent_id", String(32)),
    Column("kind", String(10), nullable=False),                   # run | agent | llm
    Column("name", String(100), nullable=False),                  # agent name, or "run"
    Column("model", String(120)),
    Column("attempt", Integer, nullable=False, default=1),        # >1 = rework / retry of the same agent
    Column("started_at", DateTime(timezone=True), nullable=False, index=True),
    Column("duration_ms", Integer, nullable=False, default=0),
    Column("status", String(10), nullable=False, default="ok"),  # ok | error
    Column("error", Text),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("cached_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("thinking_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float),                                    # None = model price unknown
    Column("attrs", Text),                                        # JSON: finish reason, prompt size, ...
)

_tables_ready = False
ORCHESTRATOR = "solution_advisor"


def ensure_tables() -> None:
    global _tables_ready
    if not _tables_ready:
        metadata.create_all(db.engine())
        _tables_ready = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Span:
    trace_id: str
    kind: str
    name: str
    parent_id: str | None = None
    model: str | None = None
    attempt: int = 1
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: datetime = field(default_factory=_now)
    _t0: float = field(default_factory=time.perf_counter, repr=False)
    duration_ms: int = 0
    status: str = "ok"
    error: str | None = None
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float | None = 0.0
    attrs: dict = field(default_factory=dict)

    def end(self, error: str | None = None) -> None:
        self.duration_ms = int((time.perf_counter() - self._t0) * 1000)
        if error:
            self.status, self.error = "error", error[:2000]


@dataclass
class _Run:
    root: Span
    session_id: str
    user_id: str
    spans: list[Span] = field(default_factory=list)
    agent_spans: dict[str, Span] = field(default_factory=dict)   # open agent span per agent name
    llm_spans: dict[str, Span] = field(default_factory=dict)     # open model call per agent name
    attempts: dict[str, int] = field(default_factory=dict)


def _usage(response: LlmResponse) -> dict[str, int]:
    u = response.usage_metadata
    if u is None:
        return {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
    return {"input_tokens": u.prompt_token_count or 0, "cached_tokens": u.cached_content_token_count or 0,
            "output_tokens": u.candidates_token_count or 0, "thinking_tokens": u.thoughts_token_count or 0}


def _request_chars(request: LlmRequest) -> int:
    """Size of what was sent (system prompt + messages), a hint for slow or costly calls."""
    system = request.config.system_instruction if request.config else None
    chars = len(system) if isinstance(system, str) else 0
    for content in request.contents or []:
        chars += sum(len(p.text or "") for p in content.parts or [])
    return chars


class TracingPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="advisor_tracing")
        self._runs: dict[str, _Run] = {}

    # --------------------------------------------------------------- run
    async def before_run_callback(self, *, invocation_context: InvocationContext) -> None:
        ctx = invocation_context
        root = Span(ctx.invocation_id, "run", "run")
        self._runs[ctx.invocation_id] = _Run(root, ctx.session.id, ctx.session.user_id, [root])
        return None

    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        await self._finish(invocation_context, None)

    async def on_run_error_callback(self, *, invocation_context: InvocationContext, error: Exception) -> None:
        await self._finish(invocation_context, f"{type(error).__name__}: {error}")

    async def _finish(self, ctx: InvocationContext, error: str | None) -> None:
        run = self._runs.pop(ctx.invocation_id, None)
        if run is None:
            return
        for span in [*run.llm_spans.values(), *run.agent_spans.values()]:  # anything left open was cut short
            span.end(error or "did not finish")
        run.root.end(error)
        children = [s for s in run.spans if s.kind == "llm"]
        for k in ("input_tokens", "cached_tokens", "output_tokens", "thinking_tokens"):
            setattr(run.root, k, sum(getattr(s, k) for s in children))
        costs = [s.cost_usd for s in children]
        run.root.cost_usd = None if any(c is None for c in costs) else round(sum(costs), 6)
        run.root.attrs = {"llm_calls": len(children), "unpriced_models": sorted(
            {s.model or "?" for s in children if s.cost_usd is None})}
        run_id = ctx.session.state.get("run_id")  # set by the orchestrator at the start of each turn
        event(log, logging.ERROR if error else logging.INFO, "run done", run_id=run_id, trace_id=ctx.invocation_id,
              user_id=run.user_id, duration_ms=run.root.duration_ms, llm_calls=len(children),
              input_tokens=run.root.input_tokens, output_tokens=run.root.output_tokens + run.root.thinking_tokens,
              cost_usd=run.root.cost_usd, error=error)
        try:
            await asyncio.to_thread(save, run.spans, run_id=run_id, session_id=run.session_id, user_id=run.user_id)
        except Exception:  # noqa: BLE001 - losing a trace must never break a run
            log.exception("Could not save trace %s", ctx.invocation_id)

    # ------------------------------------------------------------- agents
    async def before_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> None:
        run = self._runs.get(callback_context.invocation_id)
        if run is None:
            return None
        name = agent.name
        run.attempts[name] = run.attempts.get(name, 0) + 1
        root_agent = next((s for s in run.agent_spans.values() if s.parent_id == run.root.id), None)
        parent = run.root if root_agent is None or root_agent.name == name else root_agent
        span = Span(run.root.trace_id, "agent", name, parent.id, attempt=run.attempts[name])
        run.agent_spans[name] = span
        run.spans.append(span)
        return None

    async def after_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> None:
        self._end_agent(callback_context.invocation_id, agent.name, None)
        return None

    async def on_agent_error_callback(self, *, agent: BaseAgent, callback_context: CallbackContext,
                                      error: Exception) -> None:
        self._end_agent(callback_context.invocation_id, agent.name, f"{type(error).__name__}: {error}")
        return None

    def _end_agent(self, invocation_id: str, name: str, error: str | None) -> None:
        run = self._runs.get(invocation_id)
        span = run.agent_spans.pop(name, None) if run else None
        if span is None:
            return
        span.end(error)
        calls = [s for s in run.spans if s.kind == "llm" and _descends(s, span.id, run.spans)]
        for k in ("input_tokens", "cached_tokens", "output_tokens", "thinking_tokens"):
            setattr(span, k, sum(getattr(s, k) for s in calls))
        costs = [s.cost_usd for s in calls]
        span.cost_usd = None if any(c is None for c in costs) else round(sum(costs), 6)
        if calls:
            span.model = calls[-1].model
        event(log, logging.ERROR if error else logging.INFO, "agent done", trace_id=invocation_id, agent=name,
              attempt=span.attempt, duration_ms=span.duration_ms, llm_calls=len(calls), input_tokens=span.input_tokens,
              output_tokens=span.output_tokens + span.thinking_tokens, cost_usd=span.cost_usd, error=error)

    # -------------------------------------------------------------- model
    async def before_model_callback(self, *, callback_context: CallbackContext,
                                    llm_request: LlmRequest) -> Optional[LlmResponse]:
        run = self._runs.get(callback_context.invocation_id)
        agent = run.agent_spans.get(callback_context.agent_name) if run else None
        if agent is None:
            return None
        span = Span(run.root.trace_id, "llm", callback_context.agent_name, agent.id,
                    model=llm_request.model or "?", attempt=agent.attempt,
                    attrs={"request_chars": _request_chars(llm_request)})
        run.llm_spans[callback_context.agent_name] = span
        run.spans.append(span)
        return None

    async def after_model_callback(self, *, callback_context: CallbackContext,
                                   llm_response: LlmResponse) -> Optional[LlmResponse]:
        if llm_response.partial:
            return None  # streaming chunk; the final response carries the usage
        run = self._runs.get(callback_context.invocation_id)
        span = run.llm_spans.pop(callback_context.agent_name, None) if run else None
        if span is None:
            return None
        usage = _usage(llm_response)
        for k, v in usage.items():
            setattr(span, k, v)
        span.cost_usd = cost_usd(span.model or "", when=span.started_at, **usage)
        if llm_response.finish_reason:
            span.attrs["finish_reason"] = str(llm_response.finish_reason.value
                                              if hasattr(llm_response.finish_reason, "value")
                                              else llm_response.finish_reason)
        error = f"{llm_response.error_code}: {llm_response.error_message}" if llm_response.error_code else None
        span.end(error)
        event(log, logging.WARNING if error else logging.INFO, "model call", trace_id=span.trace_id, agent=span.name,
              model=span.model, duration_ms=span.duration_ms, input_tokens=span.input_tokens,
              cached_tokens=span.cached_tokens, output_tokens=span.output_tokens,
              thinking_tokens=span.thinking_tokens, cost_usd=span.cost_usd, error=error)
        return None

    async def on_model_error_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest,
                                      error: Exception) -> Optional[LlmResponse]:
        run = self._runs.get(callback_context.invocation_id)
        span = run.llm_spans.pop(callback_context.agent_name, None) if run else None
        if span is not None:
            span.end(f"{type(error).__name__}: {error}")
            event(log, logging.WARNING, "model call failed", trace_id=span.trace_id, agent=span.name,
                  model=span.model, duration_ms=span.duration_ms, error=span.error)
        return None


def _descends(span: Span, ancestor_id: str, spans: list[Span]) -> bool:
    """True if `span` sits anywhere below `ancestor_id` (the orchestrator totals all its sub-agents)."""
    parents = {s.id: s.parent_id for s in spans}
    node = span.parent_id
    while node:
        if node == ancestor_id:
            return True
        node = parents.get(node)
    return False


# ------------------------------------------------------------- storage
def save(spans: list[Span], *, run_id: str | None, session_id: str, user_id: str) -> None:
    ensure_tables()
    rows = []
    for s in spans:
        row = {k: v for k, v in asdict(s).items() if not k.startswith("_")}
        row.update(run_id=run_id, session_id=session_id, user_id=user_id, attrs=json.dumps(s.attrs))
        rows.append(row)
    with db.engine().begin() as conn:
        conn.execute(insert(trace_spans), rows)


def _row(r) -> dict:
    d = dict(r._mapping)
    d["attrs"] = json.loads(d["attrs"] or "{}")
    started = d["started_at"]
    d["started_at"] = (started if started.tzinfo else started.replace(tzinfo=timezone.utc)).isoformat()
    return d


def run_trace(run_id: str) -> list[dict]:
    """All spans of the turn(s) that produced this run, oldest first."""
    ensure_tables()
    with db.engine().connect() as conn:
        rows = conn.execute(select(trace_spans).where(trace_spans.c.run_id == run_id)
                            .order_by(trace_spans.c.started_at)).all()
    return [_row(r) for r in rows]


def run_summaries(run_ids: list[str]) -> dict[str, dict]:
    """run_id -> {duration_ms, tokens, cost_usd} from the run-level spans."""
    if not run_ids:
        return {}
    ensure_tables()
    with db.engine().connect() as conn:
        rows = conn.execute(
            select(trace_spans.c.run_id, func.sum(trace_spans.c.duration_ms),
                   func.sum(trace_spans.c.input_tokens + trace_spans.c.output_tokens + trace_spans.c.thinking_tokens),
                   func.sum(trace_spans.c.cost_usd), func.count(), func.count(trace_spans.c.cost_usd))
            .where(trace_spans.c.kind == "run", trace_spans.c.run_id.in_(run_ids))
            .group_by(trace_spans.c.run_id)).all()
    return {r[0]: {"duration_ms": int(r[1] or 0), "tokens": int(r[2] or 0),
                   # a sum over partly unpriced runs would understate the cost
                   "cost_usd": round(r[3], 6) if r[3] is not None and r[4] == r[5] else None} for r in rows}


def usage(days: int) -> dict:
    """Totals for the last `days` days: overall, per user, per model, per agent, and outlier runs."""
    ensure_tables()
    since = _now() - timedelta(days=days)
    t = trace_spans
    tokens = t.c.input_tokens + t.c.output_tokens + t.c.thinking_tokens
    with db.engine().connect() as conn:
        def grouped(column, kind: str, *extra) -> list[dict]:
            rows = conn.execute(
                select(column, func.count(), func.sum(t.c.duration_ms), func.sum(tokens), func.sum(t.c.cost_usd),
                       func.count(t.c.cost_usd))
                .where(t.c.kind == kind, t.c.started_at >= since, *extra).group_by(column)
                .order_by(func.sum(t.c.cost_usd).desc().nulls_last(), func.sum(tokens).desc())).all()
            return [{"key": r[0], "count": r[1], "duration_ms": int(r[2] or 0), "tokens": int(r[3] or 0),
                     "cost_usd": round(r[4] or 0, 6), "unpriced": r[1] - r[5]} for r in rows]

        def top(order) -> list[dict]:
            rows = conn.execute(select(t.c.run_id, t.c.user_id, t.c.duration_ms, tokens, t.c.cost_usd, t.c.started_at)
                                .where(t.c.kind == "run", t.c.run_id.is_not(None), t.c.started_at >= since)
                                .order_by(*(order if isinstance(order, tuple) else (order,))).limit(5)).all()
            return [{"run_id": r[0], "user_id": r[1], "duration_ms": r[2], "tokens": int(r[3] or 0),
                     "cost_usd": r[4], "started_at": _row_time(r[5])} for r in rows]

        return {
            "days": days,
            "totals": (grouped(t.c.kind, "run") or [{"count": 0, "duration_ms": 0, "tokens": 0, "cost_usd": 0,
                                                     "unpriced": 0}])[0],
            "by_user": grouped(t.c.user_id, "run"),
            "by_model": grouped(t.c.model, "llm"),
            # The orchestrator's span already totals its sub-agents; listing it would double-count.
            "by_agent": grouped(t.c.name, "agent", t.c.name != ORCHESTRATOR),
            "slowest": top(t.c.duration_ms.desc()),
            "most_expensive": top((t.c.cost_usd.desc().nulls_last(), tokens.desc())),
        }


def _row_time(value: Any) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
