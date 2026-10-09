"""Dynamic agent selection: a plain, explainable rule table.

Deliberately not an LLM call, so the same classification always activates the
same agents and the plan is easy to explain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Specialist agents available in the POC.
SPECIALISTS = ["frontend", "uiux", "backend", "database", "cloud", "security", "performance", "aiml"]

# domain -> agents it activates
DOMAIN_RULES: dict[str, list[str]] = {
    "frontend": ["frontend", "uiux", "performance", "security"],
    "fullstack": ["frontend", "backend", "database", "security", "performance"],
    "backend": ["backend", "database", "security", "performance"],
    "mobile": ["frontend", "uiux", "backend", "security", "performance"],
    "cloud": ["cloud", "security", "performance"],
    "aiml": ["aiml", "database", "backend", "security"],
    "data": ["database", "cloud", "security"],
    "other": ["security"],
}

@dataclass
class SelectionPlan:
    agents: list[str]
    reasons: dict[str, list[str]] = field(default_factory=dict)
    escalate: bool = False
    escalation_reason: str = ""

    def explain(self) -> str:
        lines = [f"- **{a}**: {', '.join(self.reasons.get(a, []))}" for a in self.agents]
        return "\n".join(lines)


def select_agents(domains: list[str], cloud_relevant: bool, confidence: float = 1.0) -> SelectionPlan:
    reasons: dict[str, list[str]] = {}
    for domain in domains:
        for agent in DOMAIN_RULES.get(domain, []):
            reasons.setdefault(agent, []).append(f"needed for {domain}")

    # The cloud agent runs only when cloud is actually in scope. This is what
    # keeps a frontend-only request free of cloud, DR and cost analysis.
    if cloud_relevant:
        reasons.setdefault("cloud", []).append("hosting/infrastructure is in scope")

    ordered = [a for a in SPECIALISTS if a in reasons]
    plan = SelectionPlan(agents=ordered, reasons=reasons)

    if confidence < 0.7 or domains == ["other"] or not ordered:
        plan.escalate = True
        plan.escalation_reason = (
            f"Low classification confidence ({confidence:.2f})"
            if confidence < 0.7
            else "Requirement falls outside the supported domains"
        )
    return plan
