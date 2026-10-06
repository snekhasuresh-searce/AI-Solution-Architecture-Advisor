"""Requirement Analyzer / Classifier agent."""

from google.adk.agents import LlmAgent

from .. import prompts
from ..models import strong_model
from ..schemas import AnalyzerOutput


def build_analyzer() -> LlmAgent:
    return LlmAgent(
        name="requirement_analyzer",
        description="Extracts a structured brief and classifies the solution domains.",
        model=strong_model(),
        instruction=prompts.ANALYZER,
        output_schema=AnalyzerOutput,
        output_key="analysis",
        # Default contents: sees the conversation, so answers to clarifying
        # questions in later turns are taken into account.
    )
