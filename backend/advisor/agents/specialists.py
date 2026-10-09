"""Specialist agents, built from one template.

Each specialist reads the brief (and any rework findings) from session state
through an instruction provider, and writes its JSON to state['spec_<name>'].
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from .. import prompts
from ..catalogue import catalogue_prompt
from ..models import fast_model
from ..schemas import SpecialistOutput
from ..selector import SPECIALISTS


def _instruction_for(name: str):
    def provider(ctx: ReadonlyContext) -> str:
        state = ctx.state
        brief = json.dumps(state.get("brief", {}), indent=2)
        rework = ""
        findings = state.get(f"rework_{name}")
        if findings:
            rework = prompts.REWORK_BLOCK.format(
                findings="\n".join(f"- [{f['severity']}] {f['description']} -> {f['recommendation']}" for f in findings),
                previous=json.dumps(state.get(f"spec_{name}", {}), indent=2),
            )
        return prompts.SPECIALIST_TEMPLATE.format(
            name=name,
            focus=prompts.SPECIALIST_FOCUS[name],
            brief=brief,
            catalogue=catalogue_prompt(),
            rework=rework,
        )

    return provider


def build_specialist(name: str, provider: str | None = None) -> LlmAgent:
    if name not in SPECIALISTS:
        raise ValueError(f"Unknown specialist '{name}'")
    return LlmAgent(
        name=f"{name}_agent",
        description=prompts.SPECIALIST_FOCUS[name].split(".")[0],
        model=fast_model(provider),
        instruction=_instruction_for(name),
        output_schema=SpecialistOutput,
        output_key=f"spec_{name}",
        include_contents="none",  # works from the brief, not the chat history
    )


def build_all_specialists(provider: str | None = None) -> dict[str, LlmAgent]:
    return {name: build_specialist(name, provider) for name in SPECIALISTS}
