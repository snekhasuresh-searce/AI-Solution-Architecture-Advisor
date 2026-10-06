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
    "frontend": [("Frontend framework", "Next.js", "SSR/SSG for fast, SEO-friendly pages", ["Astro", "Nuxt"]),
                 ("Styling", "Tailwind CSS", "Fast responsive layouts", ["CSS Modules"])],
    "uiux": [("Component library", "shadcn/ui", "Accessible, unstyled primitives", ["Material UI"])],
    "backend": [("API runtime", "NestJS", "Structured TypeScript services", ["FastAPI", "Express"]),
                ("API style", "REST", "Simple, well understood", ["GraphQL"])],
    "database": [("Primary database", "PostgreSQL", "Relational data with strong consistency", ["MySQL"])],
    "cloud": [("Compute", "Cloud Run", "Serverless containers, scale to zero", ["GKE"]),
              ("Database hosting", "Cloud SQL", "Managed PostgreSQL with HA", ["AlloyDB"])],
    "security": [("Authentication", "Identity Platform", "Managed authentication service", ["Auth0", "Keycloak"])],
    "performance": [("Performance testing", "Lighthouse", "Core Web Vitals checks in CI", ["k6"])],
    "aiml": [("LLM", "Gemini", "Strong reasoning, long context", ["Vertex AI"]),
             ("Vector store", "pgvector", "Keeps vectors next to app data", ["Vertex AI Vector Search"])],
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
        else:
            payload = {"note": "mock"}
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=json.dumps(payload))]))
