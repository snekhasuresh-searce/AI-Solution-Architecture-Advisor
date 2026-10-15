"""Sign-in (Google Workspace OIDC, or email + password), JWT sessions and roles.

Google (ADVISOR_AUTH_MODE=google):
  1. GET /api/auth/login        -> Google, with state, nonce and PKCE stored in oauth_states
  2. GET /api/auth/callback     -> code exchanged for an ID token, which is verified
                                   (signature, issuer, audience, expiry, nonce) and must
                                   belong to a verified account of an allowed Workspace domain
Email + password (ADVISOR_PASSWORD_AUTH=true):
  POST /api/auth/signup         -> allowed domains only; the account waits for an admin to approve it
  POST /api/auth/password-login -> scrypt-hashed passwords, failed attempts rate-limited

Every sign-in starts a session with two HttpOnly cookies:
  - access token: a JWT (HS256, ADVISOR_ACCESS_TOKEN_MINUTES) naming the user and session
  - refresh token: random, only its SHA-256 stored in auth_refresh; POST /api/auth/refresh swaps
    it for a new pair (rotation; reusing an old one revokes the session)
Each request checks the JWT and that its session is still live, so signing out, deactivation
and password resets take effect at once. Sessions end ADVISOR_SESSION_TTL_HOURS after sign-in.

Roles: consultant (own runs), reviewer (all runs), admin (all runs + user management).
ADVISOR_AUTH_MODE=dev replaces Google with a form for local development.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey, LargeBinary, MetaData, String, Table, Text,
                        delete, func, insert, select, update)

from . import db
from .config import settings

log = logging.getLogger("advisor.auth")

Role = Literal["consultant", "reviewer", "admin"]
ROLES: tuple[Role, ...] = ("consultant", "reviewer", "admin")
ACCESS_COOKIE = "advisor_access"
REFRESH_COOKIE = "advisor_refresh"
LEGACY_COOKIE = "advisor_session"  # before JWT sessions; cleared on sign-out
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "archpilot"
JWT_AUDIENCE = "archpilot-web"
REFRESH_GRACE = timedelta(seconds=30)  # another tab may still send the token that was just rotated
CLIENT_HEADER = "X-Advisor-Client"  # required on writes; a cross-site form cannot send it

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_TTL = timedelta(minutes=10)

# ----------------------------------------------------------------- tables
metadata = MetaData()

users = Table(
    "users", metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("name", String(200)),
    Column("picture", Text),  # Google photo URLs can exceed 1,000 characters
    Column("role", String(20), nullable=False, default="consultant"),
    Column("active", Boolean, nullable=False, default=True),
    Column("google_sub", String(255), unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True)),
    Column("password_hash", Text),                   # None: signs in with Google only
    Column("pending_approval", Boolean, nullable=False, default=False),  # signed up, not yet approved
    Column("picture_version", BigInteger),  # set while an uploaded photo replaces the Google one
)

# Uploaded profile photos (re-encoded 256 px WebP), in the database so every instance can serve them.
user_pictures = Table(
    "user_pictures", metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("data", LargeBinary, nullable=False),
    Column("content_type", String(50), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# One row per signed-in session (browser). The JWT access token carries its id.
auth_refresh = Table(
    "auth_refresh", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("previous_hash", String(64), index=True),  # the token it replaced, accepted briefly
    Column("rotated_at", DateTime(timezone=True)),
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


_tables_lock = threading.Lock()


def ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:  # concurrent first requests must not create or alter the tables at the same time
        if _tables_ready:
            return
        engine = db.engine()
        metadata.create_all(engine)
        _widen_picture_column(engine)
        _add_user_columns(engine)
        _tables_ready = True


def _add_user_columns(engine) -> None:
    """Add columns to users tables created before email + password sign-in and photo uploads."""
    from sqlalchemy import inspect

    have = {c["name"] for c in inspect(engine).get_columns("users")}
    missing = [(name, ddl) for name, ddl in (("password_hash", "TEXT"),
                                             ("pending_approval", "BOOLEAN NOT NULL DEFAULT FALSE"),
                                             ("picture_version", "BIGINT"))
               if name not in have]
    with engine.begin() as conn:
        for name, ddl in missing:
            conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
            log.info("Added users.%s", name)


def _widen_picture_column(engine) -> None:
    """Older Postgres tables have users.picture as VARCHAR(1000); make it TEXT (SQLite has no limit)."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        kind = conn.exec_driver_sql(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'picture'").scalar()
        if kind == "character varying":  # only then: ALTER takes an exclusive lock on the table
            conn.exec_driver_sql("ALTER TABLE users ALTER COLUMN picture TYPE TEXT")
            log.info("Widened users.picture to TEXT")


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
    has_password: bool = False
    picture_version: int | None = None  # an uploaded photo; `picture` stays the Google one

    def can_see_all_runs(self) -> bool:
        return self.role in ("reviewer", "admin")

    @property
    def display_picture(self) -> str | None:
        """The uploaded photo (versioned URL, so browsers cache it) or else the Google photo."""
        if self.picture_version:
            return f"/api/users/{self.id}/picture?v={self.picture_version}"
        return self.picture

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "picture": self.display_picture,
                "role": self.role, "has_password": self.has_password,
                "has_custom_picture": bool(self.picture_version)}


def _user(row) -> User:
    return User(row.id, row.email, row.name, row.picture, row.role, bool(row.active), bool(row.password_hash),
                row.picture_version)


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
        if picture is None:
            del values["picture"]  # keep the saved photo when this sign-in did not supply one
        if google_sub:
            values["google_sub"] = google_sub
            if row is not None and row.pending_approval:  # Google verified the Workspace account, which
                values.update(pending_approval=False, active=True)  # is all a Google sign-in ever needs
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
    return [{**_user(r).public(), "active": bool(r.active), "pending": bool(r.pending_approval),
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
            if active:
                values["pending_approval"] = False  # activating a signup approves it
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
                conn.execute(delete(auth_refresh).where(auth_refresh.c.user_id == user_id))
            log.info("%s changed %s: %s", actor.email, row.email, values)
        updated = conn.execute(select(users).where(users.c.id == user_id)).one()
    return {**_user(updated).public(), "active": bool(updated.active), "pending": bool(updated.pending_approval)}


# --------------------------------------------------------------- sessions
_signing_key = settings.jwt_secret or secrets.token_urlsafe(48)
if not settings.jwt_secret:
    log.warning("ADVISOR_JWT_SECRET is not set: using a random key, so access tokens are renewed after a restart. "
                "Set it on any shared server (the same value on every instance).")


def issue_access_token(user: User, session_id: str) -> str:
    now = _now()
    return jwt.encode({"iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "sub": user.id, "sid": session_id,
                       "email": user.email, "role": user.role, "iat": now,
                       "exp": now + timedelta(minutes=settings.access_token_minutes)},
                      _signing_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """The token's claims, or None when it is malformed, forged or expired."""
    try:
        return jwt.decode(token, _signing_key, algorithms=[JWT_ALGORITHM], audience=JWT_AUDIENCE,
                          issuer=JWT_ISSUER, options={"require": ["exp", "sub", "sid"]})
    except jwt.PyJWTError:
        return None


def create_session(user: User, user_agent: str | None) -> tuple[str, str]:
    """A new signed-in session: returns (session id, refresh token)."""
    ensure_tables()
    session_id, refresh = str(uuid.uuid4()), secrets.token_urlsafe(32)
    with db.engine().begin() as conn:
        conn.execute(delete(auth_refresh).where(auth_refresh.c.expires_at < _now()))
        conn.execute(insert(auth_refresh).values(
            id=session_id, user_id=user.id, token_hash=_hash(refresh), created_at=_now(),
            expires_at=_now() + timedelta(hours=settings.session_ttl_hours), user_agent=(user_agent or "")[:500]))
    return session_id, refresh


def start_session(response: Response, user: User, user_agent: str | None) -> None:
    session_id, refresh = create_session(user, user_agent)
    _set_cookies(response, issue_access_token(user, session_id), refresh)


def _live_user(conn, session_id: str):
    return conn.execute(
        select(users, auth_refresh.c.expires_at)
        .join(auth_refresh, auth_refresh.c.user_id == users.c.id)
        .where(auth_refresh.c.id == session_id)
    ).first()


def user_for_access_token(token: str) -> User | None:
    claims = decode_access_token(token)
    if claims is None:
        return None
    ensure_tables()
    with db.engine().connect() as conn:  # still signed in? (sign-out, deactivation, password reset)
        row = _live_user(conn, claims["sid"])
    if row is None or row.id != claims["sub"] or _aware(row.expires_at) < _now() or not row.active:
        return None
    return _user(row)


def refresh_session(refresh: str) -> tuple[User, str, str | None] | None:
    """Swap a refresh token for (user, access token, new refresh token), or None.

    The previous token is still accepted for REFRESH_GRACE (two tabs refreshing together); then
    only a new access token is issued and the browser keeps the cookie the other tab received.
    Reusing an older token means it was copied, so the whole session is revoked."""
    ensure_tables()
    digest = _hash(refresh)
    with db.engine().begin() as conn:
        row = conn.execute(select(auth_refresh).where(auth_refresh.c.token_hash == digest)).first()
        if row is None:
            old = conn.execute(select(auth_refresh).where(auth_refresh.c.previous_hash == digest)).first()
            if old is None:
                return None
            if old.rotated_at and _now() - _aware(old.rotated_at) <= REFRESH_GRACE:
                found = _live_user(conn, old.id)
                if found is None or _aware(found.expires_at) < _now() or not found.active:
                    return None
                user = _user(found)
                return user, issue_access_token(user, old.id), None
            conn.execute(delete(auth_refresh).where(auth_refresh.c.id == old.id))
            log.warning("Refresh token reused after rotation; revoked session %s", old.id)
            return None
        found = _live_user(conn, row.id)
        if found is None or _aware(found.expires_at) < _now() or not found.active:
            conn.execute(delete(auth_refresh).where(auth_refresh.c.id == row.id))
            return None
        new_refresh = secrets.token_urlsafe(32)
        conn.execute(update(auth_refresh).where(auth_refresh.c.id == row.id).values(
            token_hash=_hash(new_refresh), previous_hash=digest, rotated_at=_now()))
        user = _user(found)
        return user, issue_access_token(user, row.id), new_refresh


def end_session(*, refresh: str | None = None, session_id: str | None = None) -> None:
    ensure_tables()
    with db.engine().begin() as conn:
        if session_id:
            conn.execute(delete(auth_refresh).where(auth_refresh.c.id == session_id))
        if refresh:
            digest = _hash(refresh)
            conn.execute(delete(auth_refresh).where((auth_refresh.c.token_hash == digest)
                                                    | (auth_refresh.c.previous_hash == digest)))


def end_all_sessions(user_id: str, *, keep: str | None = None) -> None:
    ensure_tables()
    with db.engine().begin() as conn:
        query = delete(auth_refresh).where(auth_refresh.c.user_id == user_id)
        conn.execute(query.where(auth_refresh.c.id != keep) if keep else query)


def _set_cookies(response: Response, access: str, refresh: str | None) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": settings.cookie_samesite}
    response.set_cookie(ACCESS_COOKIE, access, max_age=settings.access_token_minutes * 60, path="/api", **common)
    if refresh:  # only sent to the auth endpoints
        response.set_cookie(REFRESH_COOKIE, refresh, max_age=settings.session_ttl_hours * 3600,
                            path="/api/auth", **common)


def _clear_cookies(response: Response) -> None:
    common = {"secure": settings.cookie_secure, "samesite": settings.cookie_samesite}
    response.delete_cookie(ACCESS_COOKIE, path="/api", **common)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth", **common)
    response.delete_cookie(LEGACY_COOKIE, path="/", **common)


# ------------------------------------------------------------ dependencies
def current_user(request: Request) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user = user_for_access_token(token) if token else None
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


def current_session_id(request: Request) -> str | None:
    claims = decode_access_token(request.cookies.get(ACCESS_COOKIE) or "")
    return claims["sid"] if claims else None


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {' or '.join(roles)}")
        return user
    return dependency


# -------------------------------------------------------------- passwords
# scrypt (standard library): memory-hard, so offline guessing is slow. Stored as
# scrypt$n$r$p$salt$hash (base64), so the parameters can be raised later.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1
PASSWORD_MIN, PASSWORD_MAX = 10, 128


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        _, n, r, p, salt, digest = (stored or _DUMMY_HASH).split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return stored is not None and hmac.compare_digest(actual, expected)


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))  # same work for unknown emails: no timing hint


def check_password_rules(password: str, email: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise HTTPException(400, f"Use a password of {PASSWORD_MIN} to {PASSWORD_MAX} characters.")
    if password.strip().lower() in {email.lower(), email.split("@")[0].lower()}:
        raise HTTPException(400, "The password must not be your email address.")


# Failed password sign-ins, per email and per client IP (this process only).
_FAILS: dict[str, deque] = defaultdict(deque)
_FAIL_LIMIT, _FAIL_WINDOW = 5, 15 * 60
_fails_lock = threading.Lock()


def _throttled(*keys: str) -> bool:
    cutoff = time.monotonic() - _FAIL_WINDOW
    with _fails_lock:
        for key in keys:
            q = _FAILS[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= _FAIL_LIMIT:
                return True
    return False


def _record_failure(*keys: str) -> None:
    with _fails_lock:
        for key in keys:
            _FAILS[key].append(time.monotonic())


def _clear_failures(key: str) -> None:
    with _fails_lock:
        _FAILS.pop(key, None)


def set_password(user_id: str, password: str) -> None:
    with db.engine().begin() as conn:
        conn.execute(update(users).where(users.c.id == user_id).values(password_hash=hash_password(password)))


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


def fetch_userinfo(access_token: str | None) -> dict:
    """Profile claims (name, picture) from Google's userinfo endpoint; {} when unavailable.

    Google does not always put the profile claims in the ID token, so this fills the gaps.
    Identity and domain checks never use it: they rely on the verified ID token only."""
    if not access_token:
        return {}
    try:
        res = httpx.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception:  # noqa: BLE001 - the profile photo is optional; sign-in must not fail on it
        log.warning("Could not fetch the Google profile (userinfo)", exc_info=True)
        return {}


def _login_redirect(error: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url}/?{urlencode({'auth_error': error})}", status_code=303)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict:
    return {"mode": settings.auth_mode, "allowed_domains": list(settings.allowed_domains),
            "google_configured": bool(settings.google_client_id and settings.google_client_secret),
            "password_enabled": settings.password_auth,
            "access_token_minutes": settings.access_token_minutes}


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
        tokens = exchange_code(code, row.code_verifier)
        claims = verify_id_token(tokens["id_token"])
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
    name, picture = claims.get("name"), claims.get("picture")
    if not (name and picture):
        profile = fetch_userinfo(tokens.get("access_token"))
        name, picture = name or profile.get("name"), picture or profile.get("picture")
    user = upsert_user(email=email, name=name, picture=picture, google_sub=claims.get("sub"))
    if not user.active:
        return _login_redirect("inactive")
    response = RedirectResponse(settings.frontend_url + row.next_path, status_code=303)
    start_session(response, user, request.headers.get("user-agent"))
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
        user = replace(user, role=body.role)
    if not user.active:
        raise HTTPException(403, "This account is deactivated.")
    start_session(response, user, request.headers.get("user-agent"))
    return user.public()


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user.public()


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    end_session(refresh=request.cookies.get(REFRESH_COOKIE), session_id=current_session_id(request))
    _clear_cookies(response)
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response) -> dict:
    """New access token (and refresh token) while the session lasts; 401 once it has ended."""
    token = request.cookies.get(REFRESH_COOKIE)
    result = refresh_session(token) if token else None
    if result is None:
        _clear_cookies(response)
        raise HTTPException(401, "Session ended. Sign in again.")
    user, access, new_refresh = result
    _set_cookies(response, access, new_refresh)
    return {**user.public(), "access_token_minutes": settings.access_token_minutes}


# ---------------------------------------------------------- email + password
class Signup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=200)
    password: str = Field(max_length=PASSWORD_MAX * 4)


class PasswordLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(max_length=PASSWORD_MAX * 4)


class PasswordChange(BaseModel):
    current_password: str | None = Field(default=None, max_length=PASSWORD_MAX * 4)
    new_password: str = Field(max_length=PASSWORD_MAX * 4)


def _require_password_auth() -> None:
    if not settings.password_auth:
        raise HTTPException(404, "Not found")


@router.post("/signup", status_code=201)
def signup(body: Signup, request: Request, response: Response) -> dict:
    """Create an email + password account. It waits for an admin unless it is a bootstrap admin."""
    _require_password_auth()
    email = body.email.strip().lower()
    if "@" not in email or not domain_allowed(email):
        raise HTTPException(403, f"Use an address at {', '.join(settings.allowed_domains)}.")
    check_password_rules(body.password, email)
    ensure_tables()
    bootstrap = email in settings.admin_emails
    with db.engine().begin() as conn:
        row = conn.execute(select(users).where(users.c.email == email)).first()
        if row is not None:
            if row.password_hash:
                raise HTTPException(409, "An account with this email already exists. Sign in instead.")
            # Someone else could be signing up with this address: only its owner may add a password.
            raise HTTPException(409, "This email already signs in with Google. Sign in with Google, then set a "
                                     "password from your profile menu.")
        user_id = str(uuid.uuid4())
        conn.execute(insert(users).values(
            id=user_id, email=email, name=(body.name or "").strip() or email.split("@")[0], picture=None,
            role="admin" if bootstrap else "consultant", active=bootstrap, pending_approval=not bootstrap,
            password_hash=hash_password(body.password), created_at=_now()))
        user = _user(conn.execute(select(users).where(users.c.id == user_id)).one())
    log.info("Signed up: %s (%s)", email, "bootstrap admin" if bootstrap else "pending approval")
    if bootstrap:
        start_session(response, user, request.headers.get("user-agent"))
        return {"pending": False, "user": user.public()}
    return {"pending": True}


@router.post("/password-login")
def password_login(body: PasswordLogin, request: Request, response: Response) -> dict:
    _require_password_auth()
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "?"
    keys = (f"email:{email}", f"ip:{ip}")
    if _throttled(*keys):
        raise HTTPException(429, "Too many failed attempts. Wait 15 minutes and try again.")
    ensure_tables()
    with db.engine().connect() as conn:
        row = conn.execute(select(users).where(users.c.email == email)).first()
    if not verify_password(body.password, row.password_hash if row else None):
        _record_failure(*keys)
        raise HTTPException(401, "Incorrect email or password.")
    _clear_failures(keys[0])
    if row.pending_approval:
        raise HTTPException(403, "Your account is waiting for an admin to approve it.")
    if not row.active:
        raise HTTPException(403, "This account is deactivated.")
    with db.engine().begin() as conn:
        conn.execute(update(users).where(users.c.id == row.id).values(last_login_at=_now()))
        user = _user(conn.execute(select(users).where(users.c.id == row.id)).one())
    start_session(response, user, request.headers.get("user-agent"))
    log.info("Signed in with password: %s (%s)", user.email, user.role)
    return user.public()


@router.post("/password")
def change_password(body: PasswordChange, request: Request, user: User = Depends(current_user)) -> dict:
    """Set or change your password. Changing one needs the current password; a Google user
    adds their first password while signed in. Other sessions are signed out."""
    _require_password_auth()
    check_password_rules(body.new_password, user.email)
    with db.engine().connect() as conn:
        stored = conn.execute(select(users.c.password_hash).where(users.c.id == user.id)).scalar()
    if stored and not verify_password(body.current_password or "", stored):
        raise HTTPException(400, "The current password is incorrect.")
    set_password(user.id, body.new_password)
    end_all_sessions(user.id, keep=current_session_id(request))
    log.info("%s %s their password", user.email, "changed" if stored else "set")
    return {"ok": True}


# ---------------------------------------------------------- profile photo
PICTURE_MAX_BYTES = 5 * 1024 * 1024
PICTURE_SIZE = 256
_PICTURE_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
_PICTURE_MAX_PIXELS = 40_000_000  # refuse "decompression bombs" before decoding them


def process_picture(data: bytes) -> bytes:
    """Validate an uploaded image and re-encode it as a square WebP. Re-encoding drops any
    embedded metadata (location, camera) and anything that is not image data."""
    import io

    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in _PICTURE_FORMATS:
                raise HTTPException(400, "Use a PNG, JPEG, WebP or GIF image.")
            if probe.width * probe.height > _PICTURE_MAX_PIXELS:
                raise HTTPException(400, "That image is too large in pixels; use one under 40 megapixels.")
            image = ImageOps.exif_transpose(probe)  # phone photos: honour the camera orientation
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise HTTPException(400, "That file is not an image this app can read.") from err
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    image = ImageOps.fit(image, (PICTURE_SIZE, PICTURE_SIZE), Image.LANCZOS)  # centre crop to a square
    out = io.BytesIO()
    image.save(out, "WEBP", quality=85, method=6)
    return out.getvalue()


@router.put("/me/picture")
async def upload_picture(file: UploadFile, user: User = Depends(current_user)) -> dict:
    """Replace your profile photo (shown instead of the Google one)."""
    data = await file.read(PICTURE_MAX_BYTES + 1)
    if len(data) > PICTURE_MAX_BYTES:
        raise HTTPException(413, "The image is larger than 5 MB.")
    webp = process_picture(data)
    version = time.time_ns() // 1_000_000
    with db.engine().begin() as conn:
        conn.execute(delete(user_pictures).where(user_pictures.c.user_id == user.id))
        conn.execute(insert(user_pictures).values(user_id=user.id, data=webp, content_type="image/webp",
                                                  updated_at=_now()))
        conn.execute(update(users).where(users.c.id == user.id).values(picture_version=version))
        updated = _user(conn.execute(select(users).where(users.c.id == user.id)).one())
    log.info("%s uploaded a profile photo (%d bytes)", user.email, len(webp))
    return updated.public()


@router.delete("/me/picture")
def remove_picture(user: User = Depends(current_user)) -> dict:
    """Go back to the Google photo, or initials when there is none."""
    with db.engine().begin() as conn:
        conn.execute(delete(user_pictures).where(user_pictures.c.user_id == user.id))
        conn.execute(update(users).where(users.c.id == user.id).values(picture_version=None))
        updated = _user(conn.execute(select(users).where(users.c.id == user.id)).one())
    return updated.public()


users_router = APIRouter(prefix="/api/users", tags=["users"])


@users_router.get("/{user_id}/picture")
def user_picture(user_id: str, _: User = Depends(current_user)) -> Response:
    ensure_tables()
    with db.engine().connect() as conn:
        row = conn.execute(select(user_pictures.c.data, user_pictures.c.content_type)
                           .where(user_pictures.c.user_id == user_id)).first()
    if row is None:
        raise HTTPException(404, "No uploaded photo")
    # The URL changes with every upload (?v=...), so it can be cached for good.
    return Response(row.data, media_type=row.content_type,
                    headers={"Cache-Control": "private, max-age=31536000, immutable",
                             "X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------ admin
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: Role | None = None
    active: bool | None = None  # true also approves a pending signup


class PasswordReset(BaseModel):
    password: str = Field(max_length=PASSWORD_MAX * 4)


@admin_router.get("/users")
def admin_users(_: User = Depends(require_roles("admin"))) -> list[dict]:
    return list_users()


@admin_router.patch("/users/{user_id}")
def admin_update_user(user_id: str, body: UserUpdate, actor: User = Depends(require_roles("admin"))) -> dict:
    return update_user(user_id, role=body.role, active=body.active, actor=actor)


@admin_router.post("/users/{user_id}/password")
def admin_set_password(user_id: str, body: PasswordReset, actor: User = Depends(require_roles("admin"))) -> dict:
    """Set someone's password (e.g. they forgot it). Signs them out everywhere."""
    _require_password_auth()
    ensure_tables()
    with db.engine().connect() as conn:
        email = conn.execute(select(users.c.email).where(users.c.id == user_id)).scalar()
    if email is None:
        raise HTTPException(404, "User not found")
    check_password_rules(body.password, email)
    set_password(user_id, body.password)
    end_all_sessions(user_id)
    log.info("%s set a new password for %s", actor.email, email)
    return {"ok": True}
