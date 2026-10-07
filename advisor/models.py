"""Model factory: one switch between Gemini API, Claude (Anthropic API), Ollama and a mock model.

Use `strong_model()` for judgement-heavy agents (Analyzer, Reviewer) and
`fast_model()` for the specialists that run in parallel.
"""

from __future__ import annotations

from .config import settings


def _build(model_name: str, role: str):
    provider = settings.provider
    if provider == "claude":
        # Requires ANTHROPIC_API_KEY (or another credential the Anthropic SDK finds).
        from .claude_llm import AdvisorClaude

        effort = settings.claude_strong_effort if role == "strong" else settings.claude_fast_effort
        return AdvisorClaude(model=model_name, effort=effort)
    if provider == "gemini":
        # Requires GOOGLE_API_KEY and GOOGLE_GENAI_USE_VERTEXAI=FALSE.
        # Retry with backoff: parallel specialists often hit 503 "high demand".
        from google.adk.models import Gemini
        from google.genai import types

        return Gemini(
            model=model_name,
            retry_options=types.HttpRetryOptions(
                attempts=6, initial_delay=2, max_delay=30, http_status_codes=[429, 500, 503, 504]
            ),
        )
    if provider == "ollama":
        from google.adk.models.lite_llm import LiteLlm  # needs google-adk[extensions]

        return LiteLlm(model=model_name)
    if provider == "mock":
        from .mock_llm import MockLlm

        return MockLlm(model=f"mock-{role}")
    raise ValueError(
        f"Unknown ADVISOR_PROVIDER '{provider}'. Use gemini, claude, ollama or mock."
    )


def strong_model():
    if settings.provider == "claude":
        return _build(settings.claude_strong, "strong")
    if settings.provider == "ollama":
        return _build(settings.ollama_strong, "strong")
    return _build(settings.gemini_strong, "strong")


def fast_model():
    if settings.provider == "claude":
        return _build(settings.claude_fast, "fast")
    if settings.provider == "ollama":
        return _build(settings.ollama_fast, "fast")
    return _build(settings.gemini_fast, "fast")
