"""Delivery Estimator agent: project type, architecture, resources, effort, timeline."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from .. import prompts
from ..models import strong_model
from ..schemas import EstimationOutput


def _instruction(ctx: ReadonlyContext) -> str:
    ec = ctx.state.get("estimate_context", {})
    return prompts.ESTIMATOR.format(
        brief=json.dumps(ctx.state.get("brief", {}), indent=2),
        domains=", ".join(ctx.state.get("domains", [])),
        agents=", ".join(ec.get("agents", [])),
        solution=ec.get("solution", ""),
        review=ec.get("review", ""),
    )


def build_estimator(provider: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="estimator",
        description="Estimates the team, technical resources, effort and timeline for the reviewed solution.",
        model=strong_model(provider),
        instruction=_instruction,
        output_schema=EstimationOutput,
        output_key="estimate",
        include_contents="none",
    )
