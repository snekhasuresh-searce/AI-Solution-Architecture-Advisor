"""ADK entry point: `adk web` / `adk run` look for `root_agent` here."""

import logging

from .agents.analyzer import build_analyzer
from .agents.reviewer import build_reviewer
from .agents.specialists import build_all_specialists
from .orchestrator import AdvisorOrchestrator

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# Token-usage warnings are noise (and always fire with the mock model).
logging.getLogger("google_adk.google.adk.telemetry._metrics").setLevel(logging.ERROR)

root_agent = AdvisorOrchestrator(
    name="solution_advisor",
    analyzer=build_analyzer(),
    reviewer=build_reviewer(),
    specialists=build_all_specialists(),
)
