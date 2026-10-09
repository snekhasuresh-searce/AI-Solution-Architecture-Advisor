"""Sign-in with Google Workspace (OIDC), server-side sessions and roles.

Flow (ADVISOR_AUTH_MODE=google):
  1. GET /api/auth/login        -> Google, with state, nonce and PKCE stored in oauth_states
  2. GET /api/auth/callback     -> code exchanged for an ID token, which is verified
                                   (signature, issuer, audience, expiry, nonce) and must
                                   belong to a verified account of an allowed Workspace domain
  3. a random session token is set as an HttpOnly cookie; only its SHA-256 is stored

Roles: consultant (own runs), reviewer (all runs), admin (all runs + user management).
ADVISOR_AUTH_MODE=dev replaces Google with a form for local development.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, MetaData, String, Table, delete, func, insert, select,
                        update)

from . import db
from .config import settings

log = logging.getLogger("advisor.auth")

Role = Literal["consultant", "reviewer", "admin"]
ROLES: tuple[Role, ...] = ("consultant", "reviewer", "admin")
COOKIE = "advisor_session"
CLIENT_HEADER = "X-Advisor-Client"  # required on writes; a cross-site form cannot send it

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
STATE_TTL = timedelta(minutes=10)

# ----------------------------------------------------------------- tables
metadata = MetaData()

users = Table(
    "users", metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("name", String(200)),
    Column("picture", String(1000)),
    Column("role", String(20), nullable=False, default="consultant"),
    Column("active", Boolean, nullable=False, default=True),
    Column("google_sub", String(255), unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True)),
)

auth_sessions = Table(
    "auth_sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("user_agent", String(500)),
)

oauth_states = Table(
    "oauth_states", metadata,
    Column("state", String(64), primary_key=True),
    Column("nonce", String(64), nullable=False),
    Column("code_verifier", String(128), nullable=False),
    Column("next_path", String(500), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

_tables_ready = False


def ensure_tables() -> None:
    global _tables_ready
    if not _tables_ready:
        metadata.create_all(db.engine())
        _tables_ready = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------ users
@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str | None
    picture: str | None
    role: Role
    active: bool

    def can_see_all_runs(self) -> bool:
        return self.role in ("reviewer", "admin")

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "picture": self.picture, "role": self.role}


def _user(row) -> User:
    return User(row.id, row.email, row.name, row.picture, row.role, bool(row.active))


def domain_allowed(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in settings.allowed_domains


def upsert_user(*, email: str, name: str | None, picture: str | None, google_sub: str | None) -> User:
    """Create or refresh a user at sign-in. Bootstrap admins are always admin."""
    ensure_tables()
    email = email.lower()
    with db.engine().begin() as conn:
        # Google's sub is the stable account id; the email can change (renames).
        row = conn.execute(select(users).where(users.c.google_sub == google_sub)).first() if google_sub else None
        row = row or conn.execute(select(users).where(users.c.email == email)).first()
        values = {"email": email, "name": name, "picture": picture, "last_login_at": _now()}
        if google_sub:
            values["google_sub"] = google_sub
        if email in settings.admin_emails:
            values["role"] = "admin"
        if row is None:
            user_id = str(uuid.uuid4())
            conn.execute(insert(users).values(id=user_id, created_at=_now(), active=True,
                                              role=values.pop("role", "consultant"), **values))
        else:
            user_id = row.id
            conn.execute(update(users).where(users.c.id == user_id).values(**values))
        return _user(conn.execute(select(users).where(users.c.id == user_id)).one())


def list_users() -> list[dict]:
    ensure_tables()
    with db.engine().connect() as conn:
        rows = conn.execute(select(users).order_by(users.c.email)).all()
    return [{**_user(r).public(), "active": bool(r.active),
             "last_login_at": _aware(r.last_login_at).isoformat() if r.last_login_at else None} for r in rows]


def emails_by_id(ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    ensure_tables()
    with db.engine().connect() as conn:
        return dict(conn.execute(select(users.c.id, users.c.email).where(users.c.id.in_(ids))).all())


def update_user(user_id: str, *, role: Role | None, active: bool | None, actor: User) -> dict:
    ensure_tables()
    with db.engine().begin() as conn:
        row = conn.execute(select(users).where(users.c.id == user_id)).first()
        if row is None:
            raise HTTPException(404, "User not found")
        values: dict = {}
        if active is False and user_id == actor.id:
            raise HTTPException(400, "You cannot deactivate your own account.")
        if role is not None:
            if row.email in settings.admin_emails and role != "admin":
                raise HTTPException(400, f"{row.email} is a bootstrap admin (ADVISOR_ADMIN_EMAILS); remove it there first.")
            values["role"] = role
        if active is not None:
            values["active"] = active
        losing_admin = row.role == "admin" and row.active and (values.get("role", "admin") != "admin"
                                                                or values.get("active") is False)
        if losing_admin:
            admins = conn.execute(select(func.count()).select_from(users)
                                  .where(users.c.role == "admin", users.c.active.is_(True))).scalar_one()
            if admins <= 1:
                raise HTTPException(400, "This is the last active admin; make someone else admin first.")
        if values:
            conn.execute(update(users).where(users.c.id == user_id).values(**values))
            if values.get("active") is False:  # sign them out everywhere
                conn.execute(delete(auth_sessions).where(auth_sessions.c.user_id == user_id))
            log.info("%s changed %s: %s", actor.email, row.email, values)
        updated = conn.execute(select(users).where(users.c.id == user_id)).one()
    return {**_user(updated).public(), "active": bool(updated.active)}


# --------------------------------------------------------------- sessions
def create_session(user: User, user_agent: str | None) -> str:
    token = secrets.token_urlsafe(32)
    with db.engine().begin() as conn:
        conn.execute(delete(auth_sessions).where(auth_sessions.c.expires_at < _now()))
        conn.execute(insert(auth_sessions).values(
            token_hash=_hash(token), user_id=user.id, created_at=_now(),
            expires_at=_now() + timedelta(hours=settings.session_ttl_hours), user_agent=(user_agent or "")[:500]))
    return token


def user_for_token(token: str) -> User | None:
    ensure_tables()
    with db.engine().connect() as conn:
        row = conn.execute(
            select(users, auth_sessions.c.expires_at)
            .join(auth_sessions, auth_sessions.c.user_id == users.c.id)
            .where(auth_sessions.c.token_hash == _hash(token))
        ).first()
    if row is None or _aware(row.expires_at) < _now() or not row.active:
        return None
    return _user(row)


def end_session(token: str) -> None:
    ensure_tables()
    with db.engine().begin() as conn:
        conn.execute(delete(auth_sessions).where(auth_sessions.c.token_hash == _hash(token)))


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=settings.session_ttl_hours * 3600, httponly=True,
                        secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/")


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, samesite=settings.cookie_samesite)


# ------------------------------------------------------------ dependencies
def current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE)
    user = user_for_token(token) if token else None
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {' or '.join(roles)}")
        return user
    return dependency


# --------------------------------------------------------------- Google
def _safe_next(path: str | None) -> str:
    """Only same-site relative paths, so the redirect cannot be used to leave the app."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def exchange_code(code: str, code_verifier: str) -> dict:
    """Authorization code -> token response (contains id_token)."""
    res = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }, timeout=15)
    res.raise_for_status()
    return res.json()


def verify_id_token(token: str) -> dict:
    """Checks signature against Google's keys, issuer, audience and expiry."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, google_requests.Request(), settings.google_client_id)


def _login_redirect(error: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url}/?{urlencode({'auth_error': error})}", status_code=303)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict:
    return {"mode": settings.auth_mode, "allowed_domains": list(settings.allowed_domains),
            "google_configured": bool(settings.google_client_id and settings.google_client_secret)}


@router.get("/login")
def login(next: str | None = None) -> RedirectResponse:
    if settings.auth_mode != "google":
        raise HTTPException(400, "Google sign-in is not enabled (ADVISOR_AUTH_MODE).")
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(500, "Google sign-in is not configured: set GOOGLE_OAUTH_CLIENT_ID and _SECRET.")
    ensure_tables()
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    with db.engine().begin() as conn:
        conn.execute(delete(oauth_states).where(oauth_states.c.expires_at < _now()))
        conn.execute(insert(oauth_states).values(state=state, nonce=nonce, code_verifier=verifier,
                                                 next_path=_safe_next(next), expires_at=_now() + STATE_TTL))
    params = {
        "client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri,
        "response_type": "code", "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    }
    if len(settings.allowed_domains) == 1:
        params["hd"] = settings.allowed_domains[0]  # Google shows only that domain's accounts
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=303)


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None,
             error: str | None = None) -> RedirectResponse:
    if error or not code or not state:
        return _login_redirect("cancelled" if error == "access_denied" else "failed")
    ensure_tables()
    with db.engine().begin() as conn:  # one-time use
        row = conn.execute(select(oauth_states).where(oauth_states.c.state == state)).first()
        conn.execute(delete(oauth_states).where(oauth_states.c.state == state))
    if row is None or _aware(row.expires_at) < _now():
        return _login_redirect("expired")
    try:
        claims = verify_id_token(exchange_code(code, row.code_verifier)["id_token"])
    except Exception:  # noqa: BLE001 - never echo token errors to the browser
        log.exception("Google token exchange or verification failed")
        return _login_redirect("failed")
    if claims.get("nonce") != row.nonce:
        return _login_redirect("failed")
    email = str(claims.get("email", "")).lower()
    # hd is only present for Workspace accounts; a personal Gmail address with a
    # matching-looking email cannot pass this check.
    if not claims.get("email_verified") or str(claims.get("hd", "")).lower() not in settings.allowed_domains \
            or not domain_allowed(email):
        return _login_redirect("domain")
    user = upsert_user(email=email, name=claims.get("name"), picture=claims.get("picture"),
                       google_sub=claims.get("sub"))
    if not user.active:
        return _login_redirect("inactive")
    response = RedirectResponse(settings.frontend_url + row.next_path, status_code=303)
    _set_cookie(response, create_session(user, request.headers.get("user-agent")))
    log.info("Signed in: %s (%s)", user.email, user.role)
    return response


class DevLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = None
    role: Role | None = None


@router.post("/dev-login")
def dev_login(body: DevLogin, request: Request, response: Response) -> dict:
    """Local development only: sign in as any allowed email, optionally with a role."""
    if settings.auth_mode != "dev":
        raise HTTPException(404, "Not found")
    if not domain_allowed(body.email):
        raise HTTPException(403, f"Use an address at {', '.join(settings.allowed_domains)}.")
    user = upsert_user(email=body.email, name=body.name or body.email.split("@")[0], picture=None, google_sub=None)
    if body.role and body.role != user.role and user.email not in settings.admin_emails:
        with db.engine().begin() as conn:
            conn.execute(update(users).where(users.c.id == user.id).values(role=body.role))
        user = User(user.id, user.email, user.name, user.picture, body.role, user.active)
    if not user.active:
        raise HTTPException(403, "This account is deactivated.")
    _set_cookie(response, create_session(user, request.headers.get("user-agent")))
    return user.public()


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user.public()


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        end_session(token)
    _clear_cookie(response)
    return {"ok": True}


# ------------------------------------------------------------------ admin
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: Role | None = None
    active: bool | None = None


@admin_router.get("/users")
def admin_users(_: User = Depends(require_roles("admin"))) -> list[dict]:
    return list_users()


@admin_router.patch("/users/{user_id}")
def admin_update_user(user_id: str, body: UserUpdate, actor: User = Depends(require_roles("admin"))) -> dict:
    return update_user(user_id, role=body.role, active=body.active, actor=actor)
