"""Mock model: canned JSON so the full pipeline runs with no LLM access.

Use ADVISOR_PROVIDER=mock to check wiring, agent selection, the rework loop,
scoring and reporting before connecting a real model. The analyzer uses simple
keyword rules; specialists return fixed designs; the reviewer asks for one
security rework, then approves.
"""

from __future__ import annotations

import json
import re
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def _system_text(req: LlmRequest) -> str:
    si = req.config.system_instruction if req.config else None
    if si is None:
        return ""
    if isinstance(si, str):
        return si
    parts = getattr(si, "parts", None) or []
    return "\n".join(p.text or "" for p in parts)


def _user_text(req: LlmRequest) -> str:
    texts = []
    for c in req.contents or []:
        if c.role == "user":
            texts += [p.text for p in (c.parts or []) if getattr(p, "text", None)]
    return "\n".join(texts)


# ---------------------------------------------------------------- analyzer
def _analyze(text: str) -> dict:
    t = text.lower()
    words = re.findall(r"\w+", t)
    smalltalk = {"hi", "hello", "hey", "thanks", "thank", "you", "how", "are", "good", "morning", "ok"}
    if words and set(words) <= smalltalk:
        return {
            "is_requirement": False, "needs_clarification": False,
            "domains": ["other"], "primary_domain": "other", "cloud_relevant": False, "confidence": 0.9,
            "brief": {"title": "Greeting", "summary": text[:200]},
        }
    vague = len(words) < 8 and not any(k in t for k in ("website", "api", "rag", "saas", "gcp", "aws"))
    if vague and "assumption" not in t:
        return {
            "needs_clarification": True,
            "clarifying_questions": [
                "What problem should the application solve, and for whom?",
                "Is it a website, mobile app, API, or something else?",
                "Do you need hosting/infrastructure designed, or only the application?",
            ],
            "domains": ["other"], "primary_domain": "other", "cloud_relevant": False, "confidence": 0.3,
            "brief": {"title": "Unclear request", "summary": text[:200]},
        }

    domains: list[str] = []
    ai = any(k in t for k in ("rag", "assistant", "chatbot", "llm", " ai ", "machine learning"))
    cloud = any(k in t for k in ("aws", "gcp", "google cloud", "azure", "highly available", "infrastructure", "disaster"))
    frontend_only = ("frontend" in t or "website" in t) and any(k in t for k in ("only", "no backend"))
    backendish = any(k in t for k in ("api", "node", "postgres", "database", "saas", "authentication", "backend"))

    if ai:
        domains += ["aiml", "backend"]
    elif frontend_only:
        domains.append("frontend")
    elif backendish and any(k in t for k in ("react", "frontend", "saas", "ui")):
        domains.append("fullstack")
    elif backendish:
        domains.append("backend")
    if cloud:
        domains.append("cloud")
    if not domains:
        domains.append("frontend" if "website" in t else "other")
    return {
        "needs_clarification": False,
        "clarifying_questions": [],
        "domains": domains,
        "primary_domain": domains[0],
        "cloud_relevant": cloud,
        "confidence": 0.9,
        "brief": {
            "title": text.strip().split(".")[0][:60],
            "summary": text.strip()[:300],
            "goals": ["Deliver the requested solution"],
            "users": ["End users", "Administrators"],
            "in_scope": [f"{d} solution" for d in domains],
            "out_of_scope": [] if cloud else ["Infrastructure design"],
            "functional_requirements": ["As described in the requirement"],
            "non_functional_requirements": ["Responsive", "Secure", "Maintainable"],
            "constraints": [],
            "compliance": [],
            "expected_scale": "100,000 users" if "100,000" in t else "unknown",
            "assumptions": ["Mock analysis: replace with a real model for meaningful output"],
        },
    }


# -------------------------------------------------------------- specialists
_TECH = {
    "frontend": [("frontend_framework", "Next.js", "SSR/SSG for fast, SEO-friendly pages", ["Astro", "Nuxt"]),
                 ("styling_ui", "Tailwind CSS", "Fast responsive layouts", ["CSS Modules"])],
    "uiux": [("styling_ui", "shadcn/ui", "Accessible, unstyled primitives", ["Material UI"])],
    "backend": [("backend_runtime", "NestJS", "Structured TypeScript services", ["FastAPI", "Express"]),
                ("api_style", "REST", "Simple, well understood", ["GraphQL"])],
    "database": [("database", "PostgreSQL", "Relational data with strong consistency", ["MySQL"])],
    "cloud": [("gcp_compute_network", "Cloud Run", "Serverless containers, scale to zero", ["GKE"]),
              ("database", "Cloud SQL", "Managed PostgreSQL with HA", ["AlloyDB"])],
    "security": [("auth", "Identity Platform", "Managed authentication service", ["Auth0", "Keycloak"])],
    "performance": [("testing_quality", "Lighthouse", "Core Web Vitals checks in CI", ["k6"])],
    "aiml": [("ai_ml", "Gemini", "Strong reasoning, long context", ["Vertex AI"]),
             ("ai_ml", "pgvector", "Keeps vectors next to app data", ["Vertex AI Vector Search"])],
}


def _specialist(name: str, rework: bool) -> dict:
    notes = [f"Mock design note from the {name} agent."]
    if name == "security" and rework:
        notes.append("Added MFA for admin users and rate limiting on all authentication endpoints.")
    return {
        "agent": name,
        "summary": f"Mock {name} design for the requirement.",
        "components": [{"name": f"{name.title()} module", "responsibility": f"Handles {name} concerns"}],
        "technology_choices": [
            {"category": c, "choice": ch, "rationale": r, "alternatives": alt} for c, ch, r, alt in _TECH[name]
        ],
        "design_notes": notes,
        "risks": [{"description": f"Mock {name} risk", "severity": "low", "likelihood": "low",
                   "mitigation": "Review during pilot"}],
        "assumptions": [f"{name}: mock assumption"],
    }


# --------------------------------------------------------------- estimator
_ROLES = {  # specialist -> (role, FTE, seniority)
    "frontend": ("Frontend developer", 1, "mid"),
    "uiux": ("UI/UX designer", 0.5, "mid"),
    "backend": ("Backend developer", 1, "senior"),
    "database": ("Data engineer", 0.5, "mid"),
    "cloud": ("Cloud/DevOps engineer", 0.5, "senior"),
    "security": ("Security engineer", 0.25, "senior"),
    "aiml": ("ML engineer", 1, "senior"),
}


def _estimate(system: str) -> dict:
    m = re.search(r"## Specialist agents that designed the solution\n([^\n]*)", system)
    agents = [a.strip() for a in (m.group(1) if m else "frontend").split(",") if a.strip()]
    team = [{"role": r, "count": c, "seniority": s, "responsibilities": f"Mock: {r.lower()} work",
             "phases": ["Build"]} for a in agents if a in _ROLES for r, c, s in [_ROLES[a]]]
    team += [{"role": "QA engineer", "count": 0.5, "seniority": "mid", "responsibilities": "Mock: testing",
              "phases": ["Testing"]},
             {"role": "Project manager", "count": 0.25, "seniority": "senior", "responsibilities": "Mock: delivery",
              "phases": ["Discovery", "Build", "Testing"]}]
    builders = [t["role"] for t in team if t["role"] not in ("QA engineer", "Project manager")]
    fte = sum(t["count"] for t in team if t["role"] in builders)
    tech = [{"category": "hosting", "name": "Vercel", "purpose": "Mock hosting", "sizing": "Pro plan"},
            {"category": "testing", "name": "Playwright", "purpose": "Mock E2E tests", "sizing": "CI runs"}]
    if "aiml" in agents:
        tech.insert(0, {"category": "ai_model", "name": "Gemini", "purpose": "Mock LLM", "sizing": "~1M tokens/day"})
    return {
        "project_type": {"label": "Mock project", "complexity": "medium", "rationale": "Mock estimate."},
        "architecture": {"style": "Mock architecture", "overview": "Mock overview of the reviewed design.",
                         "layers": ["Presentation: mock", "Services: mock"]},
        "human_resources": team,
        "technical_resources": tech,
        "phases": [
            {"phase": "Discovery", "activities": ["Workshops"], "roles": [builders[0], "Project manager"],
             "effort_days_low": 3, "effort_days_likely": 5, "effort_days_high": 7, "start_week": 1,
             "duration_weeks": 1, "depends_on": []},
            {"phase": "Build", "activities": ["Implementation"], "roles": builders,
             "effort_days_low": 15 * fte, "effort_days_likely": 20 * fte, "effort_days_high": 25 * fte,
             "start_week": 2, "duration_weeks": 4, "depends_on": ["Discovery"]},
            {"phase": "Testing", "activities": ["E2E and fixes"], "roles": ["QA engineer", builders[0]],
             "effort_days_low": 5, "effort_days_likely": 7, "effort_days_high": 10, "start_week": 6,
             "duration_weeks": 2, "depends_on": ["Build"]},
        ],
        "assumptions": ["Mock estimate: replace with a real model for meaningful numbers"],
        "risks_to_estimate": ["Mock risk to estimate"],
    }


# ---------------------------------------------------------------- reviewer
def _review(system: str) -> dict:
    m = re.search(r"Score ONLY these dimensions, 0-100: ([^\n]+)\.", system)
    dims = [d.strip() for d in m.group(1).split(",")] if m else ["requirement_fit"]
    fixed = "MFA" in system
    scores = [{"dimension": d, "score": 88 if fixed else 74, "comment": "mock"} for d in dims]
    if fixed:
        return {"decision": "APPROVED", "summary": "Solution matches the scope; security gap closed.",
                "findings": [{"severity": "low", "area": "Documentation", "description": "Add a component diagram",
                              "responsible_agent": "frontend", "recommendation": "Include a diagram"}],
                "scores": scores}
    return {"decision": "REWORK", "summary": "Authentication hardening is missing.",
            "findings": [{"severity": "high", "area": "Security",
                          "description": "No MFA or rate limiting on authentication endpoints",
                          "responsible_agent": "security",
                          "recommendation": "Add MFA for privileged users and rate limiting"}],
            "scores": scores}


class MockLlm(BaseLlm):
    model: str = "mock"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"mock-.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        system = _system_text(llm_request)
        role = re.search(r"ROLE:\s*([\w:]+)", system)
        role = role.group(1) if role else ""
        if role == "analyzer":
            payload = _analyze(_user_text(llm_request))
        elif role.startswith("specialist:"):
            name = role.split(":", 1)[1]
            payload = _specialist(name, rework="Reviewer findings you must fix" in system)
        elif role == "reviewer":
            payload = _review(system)
        elif role == "estimator":
            payload = _estimate(system)
        else:
            payload = {"note": "mock"}
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=json.dumps(payload))]))
