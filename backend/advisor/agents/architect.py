"""Solution Architect agent: high-level architecture (layers, flows, traceability).

Runs once after the review loop, on the final specialist outputs, and writes
its JSON to state['architecture']. The diagram itself is drawn
deterministically from that JSON by diagram.py, so it never depends on the
model producing valid graphics.
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from .. import prompts
from ..models import strong_model
from ..schemas import ArchitectureOutput


def _instruction(ctx: ReadonlyContext) -> str:
    ac = ctx.state.get("architect_context", {})
    return prompts.ARCHITECT.format(
        domains=", ".join(ctx.state.get("domains", [])),
        cloud="yes" if ac.get("cloud_relevant") else "no",
        brief=json.dumps(ctx.state.get("brief", {}), indent=2),
        requirement=ac.get("requirement", ""),
        solution=ac.get("solution", ""),
    )


def build_architect(provider: str | None = None) -> LlmAgent:
    return LlmAgent(
        name="architect",
        description="Builds the high-level solution architecture and data flows.",
        model=strong_model(provider),
        instruction=_instruction,
        output_schema=ArchitectureOutput,
        output_key="architecture",
        include_contents="none",
    )
