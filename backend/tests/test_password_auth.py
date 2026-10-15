"""Email + password sign-up and sign-in, admin approval, and the JWT access / refresh tokens."""

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from advisor import auth
from advisor.api import app

HEADERS = {"X-Advisor-Client": "test"}
PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def _no_throttle_leaks():
    auth._FAILS.clear()
    yield
    auth._FAILS.clear()


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}@searce.com"


def _client() -> TestClient:
    return TestClient(app, headers=HEADERS)


def _admin() -> TestClient:
    client = _client()
    assert client.post("/api/auth/dev-login", json={"email": _email("admin"), "role": "admin"}).status_code == 200
    return client


def _user_id(admin: TestClient, email: str) -> dict:
    return next(u for u in admin.get("/api/admin/users").json() if u["email"] == email)


def _approved(email: str, password: str = PASSWORD) -> TestClient:
    """Sign up, have an admin approve it, sign in."""
    assert _client().post("/api/auth/signup", json={"email": email, "password": password}).json() == {"pending": True}
    admin = _admin()
    assert admin.patch(f"/api/admin/users/{_user_id(admin, email)['id']}", json={"active": True}).status_code == 200
    client = _client()
    assert client.post("/api/auth/password-login", json={"email": email, "password": password}).status_code == 200
    return client


# ------------------------------------------------------------- sign-up
def test_signup_rules():
    anon = _client()
    assert anon.post("/api/auth/signup", json={"email": "x@gmail.com", "password": PASSWORD}).status_code == 403
    assert anon.post("/api/auth/signup", json={"email": _email("short"), "password": "short"}).status_code == 400
    email = _email("self")
    assert anon.post("/api/auth/signup", json={"email": email, "password": email}).status_code == 400


def test_signup_waits_for_admin_approval():
    email = _email("pending")
    anon = _client()
    assert anon.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "name": "Pat"}).status_code == 201
    res = anon.post("/api/auth/password-login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 403 and "approve" in res.json()["detail"]

    admin = _admin()
    row = _user_id(admin, email)
    assert row["pending"] and not row["active"] and row["has_password"] and row["name"] == "Pat"
    assert admin.patch(f"/api/admin/users/{row['id']}", json={"active": True}).json()["pending"] is False

    client = _client()
    assert client.post("/api/auth/password-login", json={"email": email.upper(), "password": PASSWORD}).status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["email"] == email and me["role"] == "consultant" and me["has_password"]


def test_signup_cannot_take_an_existing_email():
    email = _email("taken")
    _approved(email)
    res = _client().post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert res.status_code == 409 and "Sign in instead" in res.json()["detail"]

    google_user = _email("google")  # an account without a password (Google / dev sign-in)
    assert _client().post("/api/auth/dev-login", json={"email": google_user}).status_code == 200
    res = _client().post("/api/auth/signup", json={"email": google_user, "password": PASSWORD})
    assert res.status_code == 409 and "Google" in res.json()["detail"]


def test_bootstrap_admin_signup_is_approved(monkeypatch):
    email = _email("boss")
    monkeypatch.setattr(auth, "settings", replace(auth.settings, admin_emails=(email,)))
    client = _client()
    res = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert res.json()["pending"] is False
    assert client.get("/api/auth/me").json()["role"] == "admin"


def test_password_auth_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(auth, "settings", replace(auth.settings, password_auth=False))
    anon = _client()
    assert anon.get("/api/auth/config").json()["password_enabled"] is False
    assert anon.post("/api/auth/signup", json={"email": _email("off"), "password": PASSWORD}).status_code == 404
    assert anon.post("/api/auth/password-login", json={"email": _email("off"), "password": PASSWORD}).status_code == 404


# ------------------------------------------------------------- sign-in
def test_wrong_password_and_throttling():
    email = _email("guess")
    _approved(email)
    anon = _client()
    for _ in range(5):
        res = anon.post("/api/auth/password-login", json={"email": email, "password": "wrong-password-1"})
        assert res.status_code == 401 and res.json()["detail"] == "Incorrect email or password."
    res = anon.post("/api/auth/password-login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 429  # even the right password, until the window passes
    unknown = anon.post("/api/auth/password-login", json={"email": _email("nobody"), "password": PASSWORD})
    assert unknown.status_code == 429  # the client IP is throttled too


def test_unknown_email_gets_the_same_answer():
    res = _client().post("/api/auth/password-login", json={"email": _email("ghost"), "password": PASSWORD})
    assert res.status_code == 401 and res.json()["detail"] == "Incorrect email or password."


def test_passwords_are_hashed():
    stored = auth.hash_password(PASSWORD)
    assert PASSWORD not in stored and stored.startswith("scrypt$")
    assert auth.verify_password(PASSWORD, stored) and not auth.verify_password("other-password", stored)
    assert stored != auth.hash_password(PASSWORD)  # salted
    assert not auth.verify_password(PASSWORD, None) and not auth.verify_password(PASSWORD, "garbage")


# -------------------------------------------------------------- tokens
def test_access_token_is_a_signed_jwt():
    client = _approved(_email("jwt"))
    token = client.cookies.get(auth.ACCESS_COOKIE)
    claims = jwt.decode(token, options={"verify_signature": False})
    me = client.get("/api/auth/me").json()
    assert claims["sub"] == me["id"] and claims["email"] == me["email"] and claims["sid"]
    assert claims["exp"] - claims["iat"] == auth.settings.access_token_minutes * 60

    forged = jwt.encode({**claims, "role": "admin"}, "not-the-key", algorithm="HS256")
    bad = _client()
    bad.cookies.set(auth.ACCESS_COOKIE, forged)
    assert bad.get("/api/auth/me").status_code == 401


def test_expired_access_token_is_renewed_with_the_refresh_token():
    client = _approved(_email("renew"))
    claims = jwt.decode(client.cookies.get(auth.ACCESS_COOKIE), options={"verify_signature": False})
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    cookie = next(c for c in client.cookies.jar if c.name == auth.ACCESS_COOKIE)  # replace it, same domain and path
    client.cookies.set(auth.ACCESS_COOKIE, jwt.encode({**claims, "exp": past}, auth._signing_key, algorithm="HS256"),
                       domain=cookie.domain, path=cookie.path)
    assert client.get("/api/auth/me").status_code == 401

    old_refresh = client.cookies.get(auth.REFRESH_COOKIE)
    res = client.post("/api/auth/refresh")
    assert res.status_code == 200 and res.json()["access_token_minutes"] == auth.settings.access_token_minutes
    assert client.cookies.get(auth.REFRESH_COOKIE) != old_refresh  # rotated
    assert client.get("/api/auth/me").status_code == 200


def test_rotated_refresh_token_grace_and_reuse(monkeypatch):
    client = _approved(_email("rotate"))
    old = client.cookies.get(auth.REFRESH_COOKIE)
    assert client.post("/api/auth/refresh").status_code == 200

    other_tab = _client()  # still holds the old token: accepted briefly, gets no new refresh cookie
    other_tab.cookies.set(auth.REFRESH_COOKIE, old, path="/api/auth")
    res = other_tab.post("/api/auth/refresh")
    assert res.status_code == 200 and auth.REFRESH_COOKIE not in res.cookies

    monkeypatch.setattr(auth, "REFRESH_GRACE", timedelta(0))  # later, the old token means it was copied
    thief = _client()
    thief.cookies.set(auth.REFRESH_COOKIE, old, path="/api/auth")
    assert thief.post("/api/auth/refresh").status_code == 401
    assert client.get("/api/auth/me").status_code == 401  # the whole session is revoked
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_and_deactivation_end_the_session_at_once():
    email = _email("bye")
    client = _approved(email)
    copy = _client()
    copy.cookies.set(auth.ACCESS_COOKIE, client.cookies.get(auth.ACCESS_COOKIE), path="/api")
    assert copy.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert copy.get("/api/auth/me").status_code == 401  # the JWT is still unexpired, but its session is gone

    client = _approved_again(email)
    admin = _admin()
    admin.patch(f"/api/admin/users/{_user_id(admin, email)['id']}", json={"active": False})
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401


def _approved_again(email: str) -> TestClient:
    client = _client()
    assert client.post("/api/auth/password-login", json={"email": email, "password": PASSWORD}).status_code == 200
    return client


# ----------------------------------------------------------- passwords
def test_change_password_needs_the_current_one_and_signs_out_elsewhere():
    email = _email("change")
    here, elsewhere = _approved(email), _approved_again(email)
    new = "a-brand-new-passphrase"
    res = here.post("/api/auth/password", json={"current_password": "wrong", "new_password": new})
    assert res.status_code == 400
    assert here.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": new}).status_code == 200
    assert here.get("/api/auth/me").status_code == 200       # this session stays
    assert elsewhere.get("/api/auth/me").status_code == 401  # the others end
    assert _client().post("/api/auth/password-login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert _client().post("/api/auth/password-login", json={"email": email, "password": new}).status_code == 200


def test_google_user_can_add_a_password_while_signed_in():
    email = _email("addpw")
    client = _client()
    client.post("/api/auth/dev-login", json={"email": email})  # stands in for a Google sign-in
    assert client.get("/api/auth/me").json()["has_password"] is False
    assert client.post("/api/auth/password", json={"new_password": PASSWORD}).status_code == 200
    assert client.get("/api/auth/me").json()["has_password"] is True
    assert _client().post("/api/auth/password-login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_admin_password_reset():
    email = _email("forgot")
    user = _approved(email)
    admin = _admin()
    uid = _user_id(admin, email)["id"]
    consultant = _approved(_email("nosy"))
    assert consultant.post(f"/api/admin/users/{uid}/password", json={"password": "x" * 12}).status_code == 403
    assert admin.post(f"/api/admin/users/{uid}/password", json={"password": "short"}).status_code == 400
    assert admin.post(f"/api/admin/users/{uid}/password", json={"password": "reset-by-admin-1"}).status_code == 200
    assert user.get("/api/auth/me").status_code == 401  # signed out everywhere
    assert _client().post("/api/auth/password-login",
                          json={"email": email, "password": "reset-by-admin-1"}).status_code == 200


def test_google_sign_in_approves_a_pending_signup(monkeypatch):
    email = _email("both")
    _client().post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    user = auth.upsert_user(email=email, name="Both", picture=None, google_sub=uuid.uuid4().hex)
    assert user.active and user.has_password
    assert _client().post("/api/auth/password-login", json={"email": email, "password": PASSWORD}).status_code == 200
