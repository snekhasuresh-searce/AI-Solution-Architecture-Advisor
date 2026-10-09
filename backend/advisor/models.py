"""Model factory: one switch between Gemini API, Claude (Anthropic API), Ollama and a mock model.

Use `strong_model()` for judgement-heavy agents (Analyzer, Reviewer) and
`fast_model()` for the specialists that run in parallel.
"""

from __future__ import annotations

from .config import settings


def _build(model_name: str, role: str, provider: str):
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


def strong_model(provider: str | None = None):
    """Model for judgement-heavy agents; `provider` overrides ADVISOR_PROVIDER (the web app's model switch)."""
    provider = provider or settings.provider
    if provider == "claude":
        return _build(settings.claude_strong, "strong", provider)
    if provider == "ollama":
        return _build(settings.ollama_strong, "strong", provider)
    return _build(settings.gemini_strong, "strong", provider)


def fast_model(provider: str | None = None):
    provider = provider or settings.provider
    if provider == "claude":
        return _build(settings.claude_fast, "fast", provider)
    if provider == "ollama":
        return _build(settings.ollama_fast, "fast", provider)
    return _build(settings.gemini_fast, "fast", provider)


def model_names(provider: str) -> dict[str, str]:
    """Model ids a provider uses, for display."""
    return {"claude": {"strong": settings.claude_strong, "fast": settings.claude_fast},
            "ollama": {"strong": settings.ollama_strong, "fast": settings.ollama_fast},
            "mock": {"strong": "mock-strong", "fast": "mock-fast"}}.get(
        provider, {"strong": settings.gemini_strong, "fast": settings.gemini_fast})
