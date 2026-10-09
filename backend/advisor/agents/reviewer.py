"""Reviewer agent: findings with severity, scores, APPROVED/REWORK."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from .. import prompts
from ..models import strong_model
from ..schemas import ReviewOutput


def _instruction(ctx: ReadonlyContext) -> str:
    rc = ctx.state.get("review_context", {})
    return prompts.REVIEWER.format(
        agents=", ".join(rc.get("agents", [])),
        dimensions=", ".join(rc.get("dimensions", [])),
        brief=json.dumps(ctx.state.get("brief", {}), indent=2),
        solution=rc.get("solution", ""),
        auto_checks=rc.get("auto_checks", "none"),
    )


def build_reviewer(provider: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="reviewer",
        description="Reviews the combined solution against the original requirement.",
        model=strong_model(provider),
        instruction=_instruction,
        output_schema=ReviewOutput,
        output_key="review",
        include_contents="none",
    )
