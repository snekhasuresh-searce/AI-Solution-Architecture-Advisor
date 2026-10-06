"""Approved technology catalogue: prompt text + hallucination check."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_CATALOGUE_PATH = Path(__file__).parent / "data" / "catalogue.json"


@lru_cache(maxsize=1)
def load_catalogue() -> dict[str, list[str]]:
    with _CATALOGUE_PATH.open(encoding="utf-8") as f:
        return json.load(f)["categories"]


def all_technologies() -> list[str]:
    return sorted({t for items in load_catalogue().values() for t in items}, key=str.lower)


def catalogue_prompt() -> str:
    """Compact catalogue text injected into specialist prompts."""
    lines = [f"- {cat}: {', '.join(items)}" for cat, items in load_catalogue().items()]
    return "\n".join(lines)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+/#.]+", " ", text.lower()).strip()


def is_known(choice: str) -> bool:
    """True if the choice names at least one catalogue technology.

    Matching is on whole words, so 'React with Next.js' is known,
    while 'Reactor' is not.
    """
    text = f" {_norm(choice)} "
    return any(f" {_norm(t)} " in text for t in all_technologies())


def unknown_choices(choices: list[str]) -> list[str]:
    return [c for c in choices if c and not is_known(c)]
