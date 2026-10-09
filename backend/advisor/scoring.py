"""Quality score: weights per project type + approval rules.

Weights follow 'D3. Approval threshold and weighting' in the requirements doc.
Only dimensions that apply to the project are scored.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import settings

WEIGHTS: dict[str, dict[str, int]] = {
    "frontend": {"requirement_fit": 25, "architecture": 20, "security": 15, "performance": 15, "maintainability": 10, "accessibility": 15},
    "mobile": {"requirement_fit": 25, "architecture": 20, "security": 15, "performance": 15, "maintainability": 15, "accessibility": 10},
    "backend": {"requirement_fit": 25, "architecture": 20, "security": 20, "performance": 15, "maintainability": 10, "scalability": 10},
    "fullstack": {"requirement_fit": 25, "architecture": 20, "security": 15, "performance": 15, "reliability": 10, "maintainability": 15},
    "cloud": {"requirement_fit": 20, "architecture": 15, "security": 20, "performance": 10, "reliability": 20, "cost": 15},
    "aiml": {"requirement_fit": 25, "architecture": 15, "security": 20, "performance": 10, "cost": 15, "maintainability": 15},
    "data": {"requirement_fit": 20, "architecture": 20, "security": 15, "reliability": 20, "cost": 15, "scalability": 10},
}
DEFAULT_WEIGHTS = {"requirement_fit": 30, "architecture": 25, "security": 25, "maintainability": 20}


def combined_weights(domains: list[str]) -> dict[str, float]:
    """Average the weights of every detected domain, rescaled to 100."""
    tables = [WEIGHTS[d] for d in domains if d in WEIGHTS] or [DEFAULT_WEIGHTS]
    dims = {k for t in tables for k in t}
    avg = {k: sum(t.get(k, 0) for t in tables) / len(tables) for k in dims}
    total = sum(avg.values())
    return {k: round(v * 100 / total, 2) for k, v in avg.items()}


@dataclass
class ScoreResult:
    overall: float
    weights: dict[str, float]
    scores: dict[str, int]
    approved: bool
    blockers: list[str]


def evaluate(domains: list[str], scores: dict[str, int], severities: list[str]) -> ScoreResult:
    weights = combined_weights(domains)
    scored = {k: w for k, w in weights.items() if k in scores}
    total_w = sum(scored.values()) or 1
    overall = round(sum(scores[k] * w for k, w in scored.items()) / total_w, 1)

    blockers: list[str] = []
    if "critical" in severities:
        blockers.append("critical finding open")
    if "high" in severities:
        blockers.append("high-severity finding open")
    if overall < settings.approval_overall:
        blockers.append(f"overall score {overall} < {settings.approval_overall}")
    fit = scores.get("requirement_fit")
    if fit is not None and fit < settings.approval_requirement_fit:
        blockers.append(f"requirement fit {fit} < {settings.approval_requirement_fit}")
    for dim in weights:
        if dim in scores and scores[dim] < settings.min_subscore:
            blockers.append(f"{dim} {scores[dim]} < {settings.min_subscore}")
    missing = [d for d in weights if d not in scores]
    if missing:
        blockers.append(f"not scored: {', '.join(missing)}")

    return ScoreResult(overall, weights, scores, approved=not blockers, blockers=blockers)
