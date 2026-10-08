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
# Solution Architect (high-level architecture diagram + presales narrative)
# --------------------------------------------------------------------------
# Logical layers of the diagram, in drawing order.
Layer = Literal[
    "users", "application", "api", "ai", "data", "integrations", "infrastructure", "security", "operations"
]
# What a box is; drives its colour/shape so client, proposed, third-party, cloud,
# AI and data components are told apart at a glance.
NodeKind = Literal["actor", "client_system", "proposed", "third_party", "cloud_service", "ai", "data_store"]


class ArchNode(BaseModel):
    id: str = Field(description="Short unique snake_case id, e.g. api_gateway")
    label: str = Field(description="Box label, 2-4 words, e.g. 'API Gateway'")
    layer: Layer
    kind: NodeKind
    technology: str = Field(default="", description="Product name, or empty if not decided")
    status: Literal["required", "recommended"] = Field(
        default="required",
        description="required = needed to meet a stated requirement; recommended = architect's proposal",
    )
    purpose: str = Field(description="One sentence: what it does and why it is needed (for AI: why AI)")


class FlowStep(BaseModel):
    source: str = Field(description="Node id")
    target: str = Field(description="Node id")
    label: str = Field(description="2-5 words, e.g. 'HTTPS request'")


class ArchFlow(BaseModel):
    name: str
    kind: Literal["request", "ai"]
    steps: list[FlowStep] = Field(default_factory=list)


class RequirementMapping(BaseModel):
    requirement: str = Field(description="A requirement from the brief, verbatim")
    components: list[str] = Field(default_factory=list, description="Node ids that deliver it")


class StackItem(BaseModel):
    layer: Layer
    technology: str
    purpose: str
    status: Literal["required", "recommended"] = "recommended"


class ArchitectureOutput(BaseModel):
    title: str
    overview: str = Field(description="Two or three sentences for non-technical stakeholders")
    cloud_provider: str = Field(description="Named provider, or 'To be confirmed' if hosting is out of scope")
    nodes: list[ArchNode]
    flows: list[ArchFlow] = Field(default_factory=list)
    requirement_mapping: list[RequirementMapping] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    technology_stack: list[StackItem] = Field(default_factory=list)
    security_considerations: list[str] = Field(default_factory=list)
    scalability_considerations: list[str] = Field(default_factory=list)
    future_enhancements: list[str] = Field(default_factory=list)
