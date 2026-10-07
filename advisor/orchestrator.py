"""Coordinator: runs the whole advisor pipeline as one custom ADK agent.

Flow per user turn:
  1. Analyzer builds the brief and classifies domains (may ask questions).
  2. Selector picks specialists from a rule table (explainable plan).
  3. Selected specialists run in parallel.
  4. Reviewer scores the combined solution; REWORK findings go back only to
     the responsible specialists, up to N rounds, then escalate to a human.
  5. Final recommendation package is saved as Markdown and logged to SQLite.

A custom BaseAgent is used (rather than fixed Sequential/Parallel/Loop agents)
because the set of specialists changes on every request.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from . import report, storage
from .catalogue import unknown_choices
from .config import settings
from .consistency import find_conflicts
from .scoring import combined_weights, evaluate
from .selector import SPECIALISTS, select_agents

log = logging.getLogger("advisor")

BLOCKING = {"critical", "high"}


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _agent_key(name: str) -> str:
    """'security_agent' / 'Security Agent' -> 'security'."""
    key = name.lower().replace(" agent", "").replace("_agent", "").strip().replace(" ", "")
    aliases = {"ui/ux": "uiux", "ux": "uiux", "ai/ml": "aiml", "ai": "aiml", "data": "database"}
    return aliases.get(key, key)


class AdvisorOrchestrator(BaseAgent):
    """Root agent. Holds every possible sub-agent; activates only what is needed."""

    analyzer: LlmAgent
    reviewer: LlmAgent
    specialists: dict[str, LlmAgent]

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, analyzer: LlmAgent, reviewer: LlmAgent, specialists: dict[str, LlmAgent]):
        super().__init__(
            name=name,
            description="AI Solution Architecture Advisor coordinator",
            analyzer=analyzer,
            reviewer=reviewer,
            specialists=specialists,
            sub_agents=[analyzer, *specialists.values(), reviewer],
        )

    # ------------------------------------------------------------------ helpers
    def _say(self, ctx: InvocationContext, text: str, state: dict | None = None) -> Event:
        return Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            actions=EventActions(state_delta=state or {}),
        )

    def _quiet(self, event: Event) -> Event:
        """Drop sub-agent JSON from the chat; keep its state_delta (output_key).

        Set ADVISOR_SHOW_AGENT_OUTPUTS=true to see the raw JSON in the chat again.
        """
        if settings.show_agent_outputs or event.author == self.name or not event.content:
            return event
        return event.model_copy(update={"content": None})

    def _set_state(self, ctx: InvocationContext, state: dict) -> Event:
        return Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            actions=EventActions(state_delta=state),
        )

    async def _run_parallel(self, agents: list[BaseAgent], ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Run several sub-agents concurrently and stream their events."""
        queue: asyncio.Queue = asyncio.Queue()
        done = object()

        async def pump(agent: BaseAgent) -> None:
            try:
                async for event in agent.run_async(ctx):
                    await queue.put(event)
            except Exception as exc:  # surface errors from any branch
                await queue.put(exc)
            finally:
                await queue.put(done)

        tasks = [asyncio.create_task(pump(a)) for a in agents]
        finished = 0
        errors: list[Exception] = []
        while finished < len(tasks):
            item = await queue.get()
            if item is done:
                finished += 1
            elif isinstance(item, Exception):
                errors.append(item)
            else:
                yield item
        await asyncio.gather(*tasks)
        if errors:
            raise errors[0]

    # --------------------------------------------------------------- main flow
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        run_id = uuid.uuid4().hex[:8]
        requirement_text = ""
        if ctx.user_content and ctx.user_content.parts:
            requirement_text = " ".join(p.text or "" for p in ctx.user_content.parts).strip()

        # 1. Analyze + classify -------------------------------------------------
        async for event in self.analyzer.run_async(ctx):
            yield self._quiet(event)
        analysis = _as_dict(ctx.session.state.get("analysis"))
        if not analysis:
            yield self._say(ctx, "The analyzer did not return a valid brief. Please rephrase the requirement.")
            return

        # Greetings / small talk: introduce the advisor instead of designing for "nothing".
        if analysis.get("is_requirement") is False:
            yield self._say(
                ctx,
                "Hi! I'm the AI Solution Architecture Advisor. Describe what you want to build "
                "and I'll analyse it, run the relevant specialist agents, review the design and "
                "return a recommendation.\n\nFor example: *\"I need a responsive company website "
                "with Home, About and Contact pages. Frontend only.\"*",
            )
            return

        asked = int(ctx.session.state.get("clarification_rounds", 0))
        if analysis.get("needs_clarification") and analysis.get("clarifying_questions") and asked < 2:
            questions = "\n".join(f"{i}. {q}" for i, q in enumerate(analysis["clarifying_questions"], 1))
            yield self._say(
                ctx,
                f"Before I design anything, I need a few details:\n\n{questions}\n\n"
                "Reply with your answers (or say 'use your assumptions').",
                state={"clarification_rounds": asked + 1},
            )
            return

        brief = analysis.get("brief", {})
        domains = analysis.get("domains") or [analysis.get("primary_domain", "other")]
        cloud_relevant = bool(analysis.get("cloud_relevant"))
        confidence = float(analysis.get("confidence", 1.0))

        # 2. Select agents --------------------------------------------------------
        plan = select_agents(domains, cloud_relevant, confidence)
        skipped = [s for s in SPECIALISTS if s not in plan.agents]
        msg = (
            f"**Brief:** {brief.get('title', 'Untitled')} - {brief.get('summary', '')}\n\n"
            f"**Classified as:** {', '.join(domains)} (confidence {confidence:.2f}, "
            f"cloud {'in' if cloud_relevant else 'not in'} scope)\n\n"
            f"**Agents selected:**\n{plan.explain()}\n\n"
            f"**Not activated:** {', '.join(skipped) or 'none'}"
        )
        if plan.escalate:
            msg += f"\n\n> Human guidance recommended: {plan.escalation_reason}."
        yield self._say(ctx, msg, state={"brief": brief, "domains": domains, "selected_agents": plan.agents,
                                         "clarification_rounds": 0})
        if not plan.agents:
            return

        # 3. Specialists in parallel ---------------------------------------------
        selected = list(plan.agents)
        yield self._set_state(ctx, {f"rework_{a}": None for a in SPECIALISTS})
        async for event in self._run_parallel([self.specialists[a] for a in selected], ctx):
            yield self._quiet(event)

        # 4. Review + rework loop -------------------------------------------------
        weights = combined_weights(domains)
        history: list[dict] = []
        status = "ESCALATED"
        last_overall = None
        review: dict = {}
        result = None

        for round_no in range(1, settings.max_rework_rounds + 2):
            outputs = {a: _as_dict(ctx.session.state.get(f"spec_{a}")) for a in selected}
            choices = [t.get("choice", "") for o in outputs.values() for t in o.get("technology_choices", [])]
            unknown = unknown_choices(choices)
            auto_checks = (
                "Technologies not in the approved catalogue (flag as high, responsible = agent that chose it): "
                + ", ".join(unknown)
                if unknown else "All technology choices are in the approved catalogue."
            )
            conflicts = find_conflicts(outputs)
            if conflicts:
                auto_checks += "\nConflicting choices across agents (already raised as high findings): " + \
                    "; ".join(c["description"] for c in conflicts)
            yield self._set_state(ctx, {"review_context": {
                "agents": selected,
                "dimensions": list(weights),
                "solution": json.dumps(outputs, indent=2),
                "auto_checks": auto_checks,
            }})

            async for event in self.reviewer.run_async(ctx):
                yield self._quiet(event)
            review = _as_dict(ctx.session.state.get("review"))
            # Deterministic conflicts are added here so approval never depends on the model spotting them.
            findings = review.get("findings", []) + conflicts
            scores = {s["dimension"]: int(s["score"]) for s in review.get("scores", []) if "dimension" in s}
            result = evaluate(domains, scores, [f.get("severity", "low") for f in findings])
            approved = review.get("decision") == "APPROVED" and result.approved

            history.append({
                "round": round_no,
                "decision": "APPROVED" if approved else "REWORK",
                "overall": result.overall,
                "blockers": result.blockers,
                "findings": findings,
            })
            yield self._say(
                ctx,
                f"**Review round {round_no}:** {'APPROVED' if approved else 'REWORK'} - "
                f"score {result.overall}/100"
                + (f"; blockers: {'; '.join(result.blockers)}" if result.blockers else ""),
            )

            if approved:
                status = "APPROVED"
                break
            if round_no > settings.max_rework_rounds:
                break  # cap reached -> escalate
            if last_overall is not None and result.overall - last_overall < 2:
                yield self._say(ctx, "Score is not improving between rounds; escalating to a human architect.")
                break
            last_overall = result.overall

            # Route blocking findings to the responsible specialists.
            routed: dict[str, list[dict]] = {}
            for f in findings:
                if f.get("severity") in BLOCKING:
                    key = _agent_key(f.get("responsible_agent", ""))
                    if key not in SPECIALISTS:
                        key = "security" if "secur" in f.get("area", "").lower() else selected[0]
                    routed.setdefault(key, []).append(f)
            if not routed:
                yield self._say(ctx, "No specific findings to route; escalating to a human architect.")
                break
            for key in routed:
                if key not in selected:
                    selected.append(key)  # reviewer found a missing area
            yield self._say(
                ctx,
                "Rework sent to: " + ", ".join(f"{k} ({len(v)} finding(s))" for k, v in routed.items()),
                state={f"rework_{k}": v for k, v in routed.items()},
            )
            async for event in self._run_parallel([self.specialists[k] for k in routed], ctx):
                yield self._quiet(event)

        # 5. Final package ------------------------------------------------------
        outputs = {a: _as_dict(ctx.session.state.get(f"spec_{a}")) for a in selected}
        markdown = report.build_markdown(
            run_id=run_id,
            status=status,
            brief=brief,
            domains=domains,
            plan_text=plan.explain(),
            outputs=outputs,
            review=review,
            score=result,
            history=history,
            unknown_tech=unknown_choices(
                [t.get("choice", "") for o in outputs.values() for t in o.get("technology_choices", [])]
            ),
        )
        path = report.save(run_id, markdown)
        storage.log_run(
            run_id=run_id,
            session_id=ctx.session.id,
            requirement=requirement_text,
            domains=domains,
            agents=selected,
            status=status,
            overall=result.overall if result else None,
            rounds=len(history),
            payload={"brief": brief, "outputs": outputs, "history": history},
        )
        yield self._say(ctx, markdown + f"\n\n---\n_Saved to `{path}` (run `{run_id}`)._",
                        state={"last_run": {"run_id": run_id, "status": status}})
