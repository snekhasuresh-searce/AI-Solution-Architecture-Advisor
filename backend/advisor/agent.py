"""ADK entry point: `adk web` / `adk run` look for `root_agent` here."""

from .agents.analyzer import build_analyzer
from .agents.estimator import build_estimator
from .agents.architect import build_architect
from .agents.reviewer import build_reviewer
from .agents.specialists import build_all_specialists
from .orchestrator import AdvisorOrchestrator

from . import logs

logs.setup()

def build_root_agent(provider: str | None = None) -> AdvisorOrchestrator:
    """A full agent tree on one provider (None = ADVISOR_PROVIDER). The web app keeps one per provider."""
    return AdvisorOrchestrator(
        name="solution_advisor",
        analyzer=build_analyzer(provider),
        reviewer=build_reviewer(provider),
        estimator=build_estimator(provider),
        architect=build_architect(provider),
        specialists=build_all_specialists(provider),
    )


root_agent = build_root_agent()
