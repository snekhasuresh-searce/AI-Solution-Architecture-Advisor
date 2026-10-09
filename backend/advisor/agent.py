"""ADK entry point: `adk web` / `adk run` look for `root_agent` here."""

from .agents.analyzer import build_analyzer
from .agents.estimator import build_estimator
from .agents.architect import build_architect
from .agents.reviewer import build_reviewer
from .agents.specialists import build_all_specialists
from .orchestrator import AdvisorOrchestrator

from . import logs

logs.setup()

root_agent = AdvisorOrchestrator(
    name="solution_advisor",
    analyzer=build_analyzer(),
    reviewer=build_reviewer(),
    estimator=build_estimator(),
    architect=build_architect(),
    specialists=build_all_specialists(),
)
