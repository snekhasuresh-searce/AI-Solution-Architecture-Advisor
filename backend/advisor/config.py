"""Runtime settings, read from environment variables (.env supported)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# The backend project folder; defaults below are relative to it, so the API
# works the same whichever directory it is started from.
BACKEND_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:  # python-dotenv is optional
    pass


def _path(name: str, default: str) -> str:
    """A path setting; relative values are taken relative to the backend folder."""
    path = Path(os.getenv(name, default)).expanduser()
    return str(path if path.is_absolute() else BACKEND_DIR / path)


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

    max_rework_rounds: int = _int("ADVISOR_MAX_REWORK_ROUNDS", 3)
    approval_overall: int = _int("ADVISOR_APPROVAL_OVERALL", 80)
    approval_requirement_fit: int = _int("ADVISOR_APPROVAL_REQUIREMENT_FIT", 85)
    min_subscore: int = _int("ADVISOR_MIN_SUBSCORE", 60)

    show_agent_outputs: bool = os.getenv("ADVISOR_SHOW_AGENT_OUTPUTS", "false").strip().lower() == "true"

    # Postgres run log, e.g. postgresql://user:pass@localhost:5432/solution_advisor.
    # Empty = local SQLite file at db_path.
    database_url: str = os.getenv("ADVISOR_DATABASE_URL", "").strip()
    db_path: str = _path("ADVISOR_DB_PATH", "outputs/runs.sqlite")
    output_dir: str = _path("ADVISOR_OUTPUT_DIR", "outputs")

    # --- Sign-in ---------------------------------------------------------------
    # google = Google Workspace SSO (production); dev = pick any allowed email, for
    # local work without OAuth credentials. Never use dev on a shared server.
    auth_mode: str = os.getenv("ADVISOR_AUTH_MODE", "google").strip().lower()
    google_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    google_client_secret: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    # Must match an "Authorized redirect URI" of the OAuth client exactly.
    google_redirect_uri: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:5173/api/auth/callback")
    # Only Google Workspace accounts of these domains may sign in.
    allowed_domains: tuple[str, ...] = tuple(
        d.strip().lower() for d in os.getenv("ADVISOR_ALLOWED_DOMAINS", "searce.com").split(",") if d.strip()
    )
    # Always admin, whatever role the admin screen gives them (bootstrap admins).
    admin_emails: tuple[str, ...] = tuple(
        e.strip().lower() for e in os.getenv("ADVISOR_ADMIN_EMAILS", "").split(",") if e.strip()
    )
    # Where the browser goes after signing in or out.
    frontend_url: str = os.getenv("ADVISOR_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    session_ttl_hours: int = _int("ADVISOR_SESSION_TTL_HOURS", 12)
    # Secure cookies need HTTPS; on by default whenever the frontend is served over HTTPS.
    cookie_secure: bool = os.getenv(
        "ADVISOR_COOKIE_SECURE", "true" if os.getenv("ADVISOR_FRONTEND_URL", "").startswith("https") else "false"
    ).strip().lower() == "true"
    # lax works when frontend and API share a site; use none (with secure) for separate sites.
    cookie_samesite: str = os.getenv("ADVISOR_COOKIE_SAMESITE", "lax").strip().lower()

    # Frontend origins allowed to call the API from the browser (comma-separated).
    cors_origins: tuple[str, ...] = tuple(
        o.strip().rstrip("/")
        for o in os.getenv("ADVISOR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    )


settings = Settings()
