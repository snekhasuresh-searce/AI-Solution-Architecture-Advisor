"""Claude provider request building (no network call)."""

from anthropic import NOT_GIVEN, transform_schema
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from advisor.claude_llm import AdvisorClaude
from advisor.schemas import ReviewOutput


def _kwargs(model: AdvisorClaude, config: types.GenerateContentConfig) -> dict:
    request = LlmRequest(model=model.model, config=config)
    return model._build_anthropic_kwargs(request, [], NOT_GIVEN, NOT_GIVEN, NOT_GIVEN)


def test_output_schema_becomes_structured_output():
    model = AdvisorClaude(model="claude-opus-5-5", effort="high")
    kwargs = _kwargs(model, types.GenerateContentConfig(system_instruction="Review.", response_schema=ReviewOutput,
                                                        response_mime_type="application/json"))
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["max_tokens"] == 16000
    assert kwargs["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": transform_schema(ReviewOutput)},
    }
    # Numeric bounds (score 0-100) are moved into descriptions, which structured outputs accept.
    score = kwargs["output_config"]["format"]["schema"]["$defs"]["DimensionScore"]["properties"]["score"]
    assert "minimum" not in score and "minimum: 0" in score["description"]


def test_without_schema_only_effort_is_sent():
    kwargs = _kwargs(AdvisorClaude(model="claude-opus-5-5", effort="medium"), types.GenerateContentConfig())
    assert kwargs["output_config"] == {"effort": "medium"}
