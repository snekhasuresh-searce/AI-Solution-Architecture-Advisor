"""Claude through the Anthropic API (ADVISOR_PROVIDER=claude, ANTHROPIC_API_KEY).

ADK's AnthropicLlm already calls Claude with the official Anthropic SDK, but it
does not forward an agent's output_schema. Every agent here returns JSON that
the orchestrator parses, so this subclass sends the schema as structured
output (output_config.format): Claude's reply is then guaranteed to match it.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any, Literal, Optional

from anthropic import AsyncAnthropic, transform_schema
from google.adk.models.anthropic_llm import AnthropicLlm
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from pydantic import BaseModel

Effort = Literal["low", "medium", "high", "xhigh", "max"]


def _json_schema(config: Optional[types.GenerateContentConfig]) -> dict[str, Any] | None:
    """The agent's output schema, adapted to what structured outputs accept
    (e.g. numeric bounds move into descriptions)."""
    if not config:
        return None
    schema = config.response_schema or config.response_json_schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return transform_schema(schema)
    if isinstance(schema, dict):
        return transform_schema(schema)
    return None


class AdvisorClaude(AnthropicLlm):
    """AnthropicLlm + structured output, a fixed effort level and more retries."""

    effort: Optional[Effort] = None
    max_tokens: int = 16000
    max_retries: int = 6  # parallel specialists can hit rate limits; the SDK backs off

    def _build_anthropic_kwargs(self, llm_request: LlmRequest, *args: Any) -> dict[str, Any]:
        kwargs = super()._build_anthropic_kwargs(llm_request, *args)
        output_config = dict(kwargs.get("output_config") or {})
        if self.effort:
            output_config.setdefault("effort", self.effort)
        schema = _json_schema(llm_request.config)
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            kwargs["output_config"] = output_config
        return kwargs

    @cached_property
    def _anthropic_client(self) -> AsyncAnthropic:
        # Parent resolves and checks credentials; keep that, raise the retry count.
        client = AnthropicLlm._anthropic_client.func(self)
        return client.with_options(max_retries=self.max_retries)
