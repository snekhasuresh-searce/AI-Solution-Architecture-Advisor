"""Sign-in, roles, run visibility, admin controls and the Google OIDC callback."""

import json
import uuid
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from advisor import auth
from advisor.api import app

HEADERS = {"X-Advisor-Client": "test"}


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}@searce.com"


def signed_in(email: str, role: str | None = None) -> TestClient:
    client = TestClient(app, headers=HEADERS)
    body = {"email": email, **({"role": role} if role else {})}
    res = client.post("/api/auth/dev-login", json=body)
    assert res.status_code == 200, res.text
    return client


def _run(client: TestClient) -> tuple[str, str]:
    sid = client.post("/api/sessions").json()["session_id"]
    with client.stream("POST", f"/api/sessions/{sid}/messages",
                       json={"text": "I need a responsive company website with Home and Contact pages. Frontend only."}) as res:
        events = [json.loads(line) for line in res.iter_lines() if line]
    return sid, next(e for e in events if e["type"] == "report")["run_id"]


# ------------------------------------------------------------ basics
def test_everything_but_health_and_auth_needs_sign_in():
    anon = TestClient(app, headers=HEADERS)
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/auth/config").json()["mode"] == "dev"
    for method, path in (("get", "/api/auth/me"), ("get", "/api/runs"), ("get", "/api/scenarios"),
                         ("post", "/api/sessions"), ("get", "/api/runs/deadbeef/report"), ("get", "/api/admin/users")):
        assert getattr(anon, method)(path).status_code == 401, path


def test_writes_need_the_client_header():
    client = signed_in(_email("csrf"))
    assert client.post("/api/sessions", headers={"X-Advisor-Client": ""}).status_code == 200  # present, empty is fine
    bare = TestClient(app)
    bare.cookies = client.cookies
    res = bare.post("/api/sessions")
    assert res.status_code == 403 and "X-Advisor-Client" in res.json()["detail"]


def test_dev_login_rules_and_logout():
    anon = TestClient(app, headers=HEADERS)
    assert anon.post("/api/auth/dev-login", json={"email": "someone@gmail.com"}).status_code == 403
    client = signed_in(_email("new"))
    assert client.get("/api/auth/me").json()["role"] == "consultant"  # default role
    assert signed_in("boss@searce.com").get("/api/auth/me").json()["role"] == "admin"  # bootstrap admin
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# ------------------------------------------------------------- roles
def test_run_visibility_by_role():
    owner_email = _email("owner")
    owner, other = signed_in(owner_email), signed_in(_email("other"))
    reviewer = signed_in(_email("reviewer"), role="reviewer")
    sid, run_id = _run(owner)

    assert [r["run_id"] for r in owner.get("/api/runs").json()][0] == run_id
    assert run_id not in [r["run_id"] for r in other.get("/api/runs").json()]
    for path in (f"/api/runs/{run_id}/report", f"/api/runs/{run_id}/export/pdf", f"/api/runs/{run_id}/diagram.svg"):
        assert other.get(path).status_code == 404, path
        assert reviewer.get(path).status_code == 200, path
    # Nobody can continue someone else's conversation.
    assert other.post(f"/api/sessions/{sid}/messages", json={"text": "hi"}).status_code == 404

    listed = {r["run_id"]: r for r in reviewer.get("/api/runs").json()}
    assert listed[run_id]["owner"] == owner_email
    assert run_id not in [r["run_id"] for r in reviewer.get("/api/runs?mine=true").json()]


def test_admin_user_management():
    admin = signed_in("boss@searce.com")
    consultant_email = _email("managed")
    consultant = signed_in(consultant_email)
    assert consultant.get("/api/admin/users").status_code == 403
    assert signed_in(_email("rev"), role="reviewer").get("/api/admin/users").status_code == 403

    target = next(u for u in admin.get("/api/admin/users").json() if u["email"] == consultant_email)
    res = admin.patch(f"/api/admin/users/{target['id']}", json={"role": "reviewer"})
    assert res.status_code == 200 and res.json()["role"] == "reviewer"
    assert consultant.get("/api/auth/me").json()["role"] == "reviewer"

    # Deactivating signs the user out everywhere.
    assert admin.patch(f"/api/admin/users/{target['id']}", json={"active": False}).json()["active"] is False
    assert consultant.get("/api/auth/me").status_code == 401
    assert TestClient(app, headers=HEADERS).post("/api/auth/dev-login",
                                                 json={"email": consultant_email}).status_code == 403

    boss = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "boss@searce.com")
    assert admin.patch(f"/api/admin/users/{boss['id']}", json={"active": False}).status_code == 400  # not yourself
    res = admin.patch(f"/api/admin/users/{boss['id']}", json={"role": "consultant"})
    assert res.status_code == 400 and "bootstrap admin" in res.json()["detail"]
    assert admin.patch(f"/api/admin/users/{boss['id']}", json={"role": "superuser"}).status_code == 422


def test_last_admin_cannot_be_removed(monkeypatch):
    """On a fresh database with no bootstrap admins, the only admin cannot be demoted or deactivated."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from advisor import db

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", lambda: engine)
    monkeypatch.setattr(auth, "_tables_ready", False)
    monkeypatch.setattr(auth, "settings", replace(auth.settings, admin_emails=()))

    only = auth.upsert_user(email="only@searce.com", name="Only", picture=None, google_sub=None)
    other = auth.upsert_user(email="other@searce.com", name="Other", picture=None, google_sub=None)
    auth.update_user(only.id, role="admin", active=None, actor=only)

    with pytest.raises(auth.HTTPException, match="last active admin"):
        auth.update_user(only.id, role="consultant", active=None, actor=only)
    auth.update_user(other.id, role="admin", active=None, actor=only)  # a second admin ...
    assert auth.update_user(only.id, role="consultant", active=None, actor=only)["role"] == "consultant"  # ... unblocks it


# ------------------------------------------------------------ Google
@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(auth, "settings", replace(auth.settings, auth_mode="google"))
    claims: dict = {}
    monkeypatch.setattr(auth, "exchange_code", lambda code, verifier: {"id_token": "token-for-" + code})
    monkeypatch.setattr(auth, "verify_id_token", lambda token: dict(claims))
    return claims


def _start(client: TestClient, next_path: str = "/") -> dict:
    res = client.get("/api/auth/login", params={"next": next_path}, follow_redirects=False)
    assert res.status_code == 303
    url = urlparse(res.headers["location"])
    assert url.netloc == "accounts.google.com"
    return {k: v[0] for k, v in parse_qs(url.query).items()}


def test_google_login_request(google):
    params = _start(TestClient(app, headers=HEADERS))
    assert params["hd"] == "searce.com" and params["code_challenge_method"] == "S256"
    assert params["scope"] == "openid email profile" and params["state"] and params["nonce"]
    assert params["redirect_uri"] == auth.settings.google_redirect_uri


def test_google_callback_success_and_replay(google):
    client = TestClient(app, headers=HEADERS)
    params = _start(client, "/runs?x=1")
    email = _email("google")
    google.update(email=email, email_verified=True, hd="searce.com", nonce=params["nonce"], sub=uuid.uuid4().hex,
                  name="Google User")
    res = client.get("/api/auth/callback", params={"code": "abc", "state": params["state"]}, follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "http://localhost:5173/runs?x=1"
    assert client.get("/api/auth/me").json()["email"] == email

    replay = TestClient(app).get("/api/auth/callback", params={"code": "abc", "state": params["state"]},
                                 follow_redirects=False)
    assert "auth_error=expired" in replay.headers["location"]  # state is single-use


@pytest.mark.parametrize("override, error", [
    ({"hd": "gmail.com"}, "domain"),
    ({"hd": None}, "domain"),                      # personal Google account
    ({"email_verified": False}, "domain"),
    ({"nonce": "forged"}, "failed"),
])
def test_google_callback_rejections(google, override, error):
    client = TestClient(app, headers=HEADERS)
    params = _start(client)
    google.update(email=_email("reject"), email_verified=True, hd="searce.com", nonce=params["nonce"], sub="s")
    google.update({k: v for k, v in override.items() if v is not None})
    for k in [k for k, v in override.items() if v is None]:
        google.pop(k, None)
    res = client.get("/api/auth/callback", params={"code": "c", "state": params["state"]}, follow_redirects=False)
    assert f"auth_error={error}" in res.headers["location"]
    assert client.get("/api/auth/me").status_code == 401


def test_google_next_cannot_leave_the_app(google):
    for evil in ("//evil.example", "https://evil.example", "\\\\evil"):
        client = TestClient(app, headers=HEADERS)
        params = _start(client, evil)
        google.update(email=_email("redir"), email_verified=True, hd="searce.com", nonce=params["nonce"], sub="r")
        res = client.get("/api/auth/callback", params={"code": "c", "state": params["state"]}, follow_redirects=False)
        assert res.headers["location"] == "http://localhost:5173/"


def test_google_account_keeps_identity_when_email_changes(google):
    sub, old, new = uuid.uuid4().hex, _email("before"), _email("after")
    ids = []
    for email in (old, new):
        client = TestClient(app, headers=HEADERS)
        params = _start(client)
        google.update(email=email, email_verified=True, hd="searce.com", nonce=params["nonce"], sub=sub)
        client.get("/api/auth/callback", params={"code": "c", "state": params["state"]}, follow_redirects=False)
        me = client.get("/api/auth/me").json()
        assert me["email"] == email
        ids.append(me["id"])
    assert ids[0] == ids[1]  # same user, so their runs stay theirs


def test_dev_login_disabled_in_google_mode(google):
    assert TestClient(app, headers=HEADERS).post("/api/auth/dev-login",
                                                 json={"email": _email("x")}).status_code == 404
