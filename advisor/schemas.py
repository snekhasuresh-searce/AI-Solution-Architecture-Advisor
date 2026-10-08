"""Structured outputs shared by every agent.

All agents return JSON matching these models, so the orchestrator can merge,
score and log results without parsing free text. Lists of small objects are
used instead of dicts because Gemini's response schemas handle them better.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .catalogue import load_catalogue

Domain =Literal["frontend", "backend", "fullstack", "mobile", "cloud", "aiml", "data", "other"]
Severity = Literal["critical", "high", "medium", "low"]
# Fixed to the catalogue's category keys so every agent uses the same names.
Category = Literal[tuple(load_catalogue())]


# --------------------------------------------------------------------------
# Requirement Analyzer / Classifier
# --------------------------------------------------------------------------
class RequirementBrief(BaseModel):
    title: str = Field(description="Short name for the project")
    summary: str = Field(description="Two or three sentences restating the need")
    goals: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list, description="Who will use the solution")
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list, description="Tech, budget, team, timeline")
    compliance: list[str] = Field(default_factory=list)
    expected_scale: str = Field(default="unknown")
    assumptions: list[str] = Field(default_factory=list)


class AnalyzerOutput(BaseModel):
    is_requirement: bool = Field(
        default=True,
        description="False for greetings, small talk or questions that describe no software to design",
    )
    needs_clarification: bool = Field(
        description="True only if critical information is missing and no sensible assumption can be made"
    )
    clarifying_questions: list[str] = Field(default_factory=list)
    domains: list[Domain] = Field(description="All solution domains that apply")
    primary_domain: Domain
    cloud_relevant: bool = Field(description="True only if hosting/infrastructure design is actually requested")
    confidence: float = Field(ge=0, le=1, description="Confidence in the classification")
    brief: RequirementBrief


# --------------------------------------------------------------------------
# Specialist agents
# --------------------------------------------------------------------------
class Component(BaseModel):
    name: str
    responsibility: str


class TechnologyChoice(BaseModel):
    category: Category = Field(description="The catalogue category the technology is listed under")
    choice: str = Field(description="The recommended technology, by its product name")
    rationale: str
    alternatives: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    description: str
    severity: Severity
    likelihood: Literal["high", "medium", "low"] = "medium"
    mitigation: str


class SpecialistOutput(BaseModel):
    agent: str
    summary: str
    components: list[Component] = Field(default_factory=list)
    technology_choices: list[TechnologyChoice] = Field(default_factory=list)
    design_notes: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Reviewer
# --------------------------------------------------------------------------
class Finding(BaseModel):
    severity: Severity
    area: str
    description: str
    responsible_agent: str = Field(description="Name of the specialist agent that should fix it")
    recommendation: str


class DimensionScore(BaseModel):
    dimension: Literal[
        "requirement_fit",
        "architecture",
        "security",
        "performance",
        "reliability",
        "cost",
        "maintainability",
        "accessibility",
        "scalability",
    ]
    score: int = Field(ge=0, le=100)
    comment: str = ""


class ReviewOutput(BaseModel):
    decision: Literal["APPROVED", "REWORK"]
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    scores: list[DimensionScore] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Estimator: project type, architecture, resources, effort, timeline
# --------------------------------------------------------------------------
Complexity = Literal["small", "medium", "large", "enterprise"]


class ProjectType(BaseModel):
    label: str = Field(description="Plain-language type, e.g. 'Static marketing website (frontend only)'")
    complexity: Complexity
    rationale: str = Field(description="One sentence on why this complexity")


class Architecture(BaseModel):
    style: str = Field(description="Architecture style, e.g. 'Jamstack static site', 'Modular monolith', "
                                   "'Serverless microservices', 'RAG pipeline'")
    overview: str = Field(description="Three to five sentences: how the parts fit and how data flows")
    layers: list[str] = Field(default_factory=list, description="Main layers or tiers, each 'Name: what it does'")


class HumanResource(BaseModel):
    role: str = Field(description="e.g. 'Frontend developer', 'ML engineer', 'QA engineer', 'Project manager'")
    count: float = Field(ge=0.1, le=50, description="Headcount in full-time equivalents; 0.5 = half time")
    seniority: Literal["junior", "mid", "senior", "lead"]
    responsibilities: str
    phases: list[str] = Field(default_factory=list, description="Phase names this role works in")


class TechnicalResource(BaseModel):
    category: Literal["ai_model", "ai_service", "cloud_compute", "cloud_storage", "database", "hosting",
                      "dev_tooling", "testing", "monitoring", "environment", "third_party_service", "other"]
    name: str = Field(description="Product or resource name; use catalogue names where they exist")
    purpose: str
    sizing: str = Field(description="Tier, size or quantity, e.g. '2 vCPU / 4 GB, min 1 instance', "
                                    "'~50k requests/month', 'dev + staging + prod'")


class PhaseEstimate(BaseModel):
    phase: str = Field(description="e.g. 'Discovery & design', 'Frontend build', 'Testing & hardening', 'Launch'")
    activities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list, description="Roles from human_resources working in this phase")
    effort_days_low: float = Field(ge=0, description="Person-days, optimistic")
    effort_days_likely: float = Field(ge=0, description="Person-days, most likely")
    effort_days_high: float = Field(ge=0, description="Person-days, pessimistic")
    start_week: int = Field(ge=1, description="Week the phase starts; phases may overlap")
    duration_weeks: float = Field(ge=0.5, description="Calendar weeks for the phase with the proposed team")
    depends_on: list[str] = Field(default_factory=list, description="Phases that must finish first")


class EstimationOutput(BaseModel):
    project_type: ProjectType
    architecture: Architecture
    human_resources: list[HumanResource]
    technical_resources: list[TechnicalResource]
    phases: list[PhaseEstimate]
    assumptions: list[str] = Field(default_factory=list)
    risks_to_estimate: list[str] = Field(default_factory=list, description="What could make it take longer")
