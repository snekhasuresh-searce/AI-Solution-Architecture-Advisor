"""Runtime settings, read from environment variables (.env supported)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv("ADVISOR_PROVIDER", "mock").strip().lower()

    gemini_strong: str = os.getenv("GEMINI_STRONG_MODEL", "gemini-3.8-flash")
    gemini_fast: str = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")

    # Claude via the Anthropic API (ANTHROPIC_API_KEY). Effort: low | medium | high | xhigh | max.
    claude_strong: str = os.getenv("CLAUDE_STRONG_MODEL", "claude-opus-5-5")
    claude_fast: str = os.getenv("CLAUDE_FAST_MODEL", "claude-opus-5-5")
    claude_strong_effort: str = os.getenv("CLAUDE_STRONG_EFFORT", "high").strip().lower()
    claude_fast_effort: str = os.getenv("CLAUDE_FAST_EFFORT", "medium").strip().lower()

    ollama_strong: str = os.getenv("OLLAMA_STRONG_MODEL", "ollama_chat/qwen2.5:14b")
    ollama_fast: str = os.getenv("OLLAMA_FAST_MODEL", "ollama_chat/qwen2.5:7b")

    # Monthly token budgets (0 = unset). The providers' APIs do not expose an account balance, so the
    # "remaining" figure in the web app is budget minus the tokens this app has used this month.
    gemini_token_budget: int = _int("GEMINI_TOKEN_BUDGET", 0)
    claude_token_budget: int = _int("CLAUDE_TOKEN_BUDGET", 0)

    max_rework_rounds: int = _int("ADVISOR_MAX_REWORK_ROUNDS", 3)
    approval_overall: int = _int("ADVISOR_APPROVAL_OVERALL", 80)
    approval_requirement_fit: int = _int("ADVISOR_APPROVAL_REQUIREMENT_FIT", 85)
    min_subscore: int = _int("ADVISOR_MIN_SUBSCORE", 60)

    show_agent_outputs: bool = os.getenv("ADVISOR_SHOW_AGENT_OUTPUTS", "false").strip().lower() == "true"

    # Postgres run log, e.g. postgresql://user:pass@localhost:5432/solution_advisor.
    # Empty = local SQLite file at db_path.
    database_url: str = os.getenv("ADVISOR_DATABASE_URL", "").strip()
    db_path: str = os.getenv("ADVISOR_DB_PATH", "outputs/runs.sqlite")
    output_dir: str = os.getenv("ADVISOR_OUTPUT_DIR", "outputs")


settings = Settings()
