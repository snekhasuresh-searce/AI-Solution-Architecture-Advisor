"""Cost of a model call from its token usage and the dated price table."""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).parent / "data" / "pricing.json"


@lru_cache(maxsize=1)
def _table() -> dict:
    with _PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _bare(model: str) -> str:
    """'models/gemini-3.8-flash' or a Vertex resource path -> 'gemini-3.8-flash'."""
    return model.rsplit("/", 1)[-1] if model.startswith(("models/", "projects/")) else model


def price(model: str, when: date | datetime | None = None) -> dict | None:
    """Per-1M-token prices in force on `when`; zeros for local/mock models; None if unknown."""
    if any(model.startswith(p) for p in _table()["free_prefixes"]):
        return {"input": 0.0, "output": 0.0, "cached_input": 0.0}
    periods = _table()["models"].get(_bare(model))
    if not periods:
        return None
    day = (when.date() if isinstance(when, datetime) else when) or date.today()
    current = None
    for p in periods:  # periods are listed oldest first
        if p["from"] is None or date.fromisoformat(p["from"]) <= day:
            current = p
    return current


def cost_usd(model: str, *, input_tokens: int, cached_tokens: int, output_tokens: int, thinking_tokens: int,
             when: date | datetime | None = None) -> float | None:
    """input_tokens includes cached_tokens (the GenAI usage shape); thinking bills as output."""
    p = price(model, when)
    if p is None:
        return None
    uncached = max(input_tokens - cached_tokens, 0)
    total = (uncached * p["input"] + cached_tokens * p["cached_input"]
             + (output_tokens + thinking_tokens) * p["output"]) / 1_000_000
    return round(total, 6)
