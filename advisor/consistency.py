"""Cross-agent consistency check: deterministic, so it does not rely on the
Reviewer model noticing that two specialists picked different products.

Only single-choice categories are checked (a site has one framework and one
host); categories such as testing_quality or database legitimately hold
several complementary technologies.
"""

from __future__ import annotations

from .catalogue import technologies_in
from .selector import SPECIALISTS

# category -> agents that own the decision, in priority order. When agents
# disagree, the first owner present wins and the others are asked to align.
SINGLE_CHOICE: dict[str, list[str]] = {
    "frontend_framework": ["frontend", "uiux"],
    "hosting_static": ["cloud", "frontend"],
}


def _picks(outputs: dict[str, dict], category: str) -> dict[str, set[str]]:
    """agent -> technologies it chose in this category."""
    picks: dict[str, set[str]] = {}
    for agent, out in outputs.items():
        for t in out.get("technology_choices", []):
            if t.get("category") == category and t.get("choice"):
                techs = technologies_in(t["choice"]) or [t["choice"].strip()]
                picks.setdefault(agent, set()).update(techs)
    return picks


def find_conflicts(outputs: dict[str, dict]) -> list[dict]:
    """High-severity findings for agents that disagree with the category owner."""
    findings: list[dict] = []
    for category, owners in SINGLE_CHOICE.items():
        picks = _picks(outputs, category)
        if len(picks) < 2:
            continue
        ordered = [a for a in owners if a in picks] + [a for a in SPECIALISTS if a in picks and a not in owners]
        owner = ordered[0]
        chosen = ", ".join(sorted(picks[owner]))
        for agent in ordered[1:]:
            if picks[agent] & picks[owner]:
                continue
            findings.append({
                "severity": "high",
                "area": "Consistency",
                "description": f"{category}: {agent} chose {', '.join(sorted(picks[agent]))} "
                               f"but {owner} (owner of this decision) chose {chosen}.",
                "responsible_agent": agent,
                "recommendation": f"Use {chosen} for {category}, or drop this choice; "
                                  "the solution must have a single one.",
            })
    return findings
