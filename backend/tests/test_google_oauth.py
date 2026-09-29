import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from backend.auth import google
from backend.auth.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from backend.auth.google_router import FLOW_COOKIE
from backend.config import get_settings
from backend.tests.test_auth_api import register, unique_email

APP = "http://localhost:3000"


@pytest.fixture
def google_enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "app_url", APP)
    return settings


def fake_google(monkeypatch, identity: google.GoogleIdentity, *, expect_nonce: bool = True):
    seen: dict = {}

    async def exchange(code: str, code_verifier: str) -> str:
        seen["code"] = code
        seen["verifier"] = code_verifier
        return "fake-id-token"

    async def verify(id_token: str, *, nonce: str) -> google.GoogleIdentity:
        seen["nonce"] = nonce
        assert id_token == "fake-id-token"
        return identity

    monkeypatch.setattr(google, "exchange_code", exchange)
    monkeypatch.setattr(google, "verify_id_token", verify)
    return seen


def identity_for(
    email: str, *, name="Test Google", verified=True, sub=None
) -> google.GoogleIdentity:
    return google.GoogleIdentity(
        sub=sub or f"sub-{uuid.uuid4().hex}",
        email=email,
        email_verified=verified,
        name=name,
        picture="https://example.test/avatar.png",
    )


async def start_flow(client: AsyncClient, next_path: str = "/dashboard") -> str:
    res = await client.get("/api/auth/google/start", params={"next": next_path})
    assert res.status_code == 303, res.text
    location = res.headers["location"]
    assert location.startswith(google.GOOGLE_AUTH_URL)
    assert FLOW_COOKIE in client.cookies
    return parse_qs(urlparse(location).query)["state"][0]


async def test_start_when_disabled_redirects_to_login(client: AsyncClient):
    res = await client.get("/api/auth/google/start")
    assert res.status_code == 303
    assert res.headers["location"].endswith("/login?error=google_disabled")


async def test_start_builds_pkce_request(client: AsyncClient, google_enabled):
    state = await start_flow(client, "/somewhere")
    res = await client.get("/api/auth/google/start", params={"next": "//evil.test"})
    q = parse_qs(urlparse(res.headers["location"]).query)
    assert q["client_id"] == ["test-client-id"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["redirect_uri"] == [f"{APP}/api/auth/google/callback"]
    assert q["scope"] == ["openid email profile"]
    assert q["state"][0] != state
    assert google.safe_next_path("//evil.test") == "/"


async def test_callback_rejects_state_mismatch(client: AsyncClient, google_enabled):
    await start_flow(client)
    res = await client.get("/api/auth/google/callback", params={"code": "c", "state": "nope"})
    assert res.status_code == 303
    assert res.headers["location"] == f"{APP}/login?error=oauth_state_mismatch"
    assert ACCESS_COOKIE not in client.cookies


async def test_callback_without_cookie(client: AsyncClient, google_enabled):
    res = await client.get("/api/auth/google/callback", params={"code": "c", "state": "s"})
    assert res.headers["location"] == f"{APP}/login?error=oauth_state_missing"


async def test_callback_user_denied(client: AsyncClient, google_enabled):
    res = await client.get("/api/auth/google/callback", params={"error": "access_denied"})
    assert res.headers["location"] == f"{APP}/login?error=google_denied"


async def test_new_google_user_gets_workspace_then_logs_in_again(
    client: AsyncClient, google_enabled, monkeypatch
):
    email = unique_email()
    identity = identity_for(email, name="Test Googler")
    seen = fake_google(monkeypatch, identity)

    state = await start_flow(client, "/dashboard")
    res = await client.get("/api/auth/google/callback", params={"code": "abc", "state": state})
    assert res.status_code == 303, res.text
    assert res.headers["location"] == f"{APP}/dashboard"
    assert seen["code"] == "abc" and seen["verifier"] and seen["nonce"]
    assert ACCESS_COOKIE in client.cookies and REFRESH_COOKIE in client.cookies
    assert FLOW_COOKIE not in client.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == email
    assert body["user"]["name"] == "Test Googler"
    assert body["user"]["avatar_url"] == identity.picture
    assert body["user"]["email_verified_at"] is not None
    assert body["org"]["role"] == "admin"
    assert body["org"]["name"] == "Test's Workspace"
    user_id = body["user"]["id"]

    client.cookies.clear()
    state = await start_flow(client, "/")
    res = await client.get("/api/auth/google/callback", params={"code": "def", "state": state})
    assert res.headers["location"] == f"{APP}/"
    again = await client.get("/api/auth/me")
    assert again.json()["user"]["id"] == user_id
    assert len(again.json()["orgs"]) == 1


async def test_google_login_activates_pending_invitation(make_client, google_enabled, monkeypatch):
    admin: AsyncClient = make_client()
    reg = await register(admin)
    invitee = unique_email()
    invited = await admin.post("/api/org/users/invite", json={"email": invitee, "role": "manager"})
    assert invited.status_code == 201

    fake_google(monkeypatch, identity_for(invitee, name="Invited Person"))
    guest: AsyncClient = make_client()
    state = await start_flow(guest)
    res = await guest.get("/api/auth/google/callback", params={"code": "x", "state": state})
    assert res.status_code == 303 and "error" not in res.headers["location"]

    me = await guest.get("/api/auth/me")
    assert me.json()["org"]["id"] == reg["org"]["id"]
    assert me.json()["org"]["role"] == "manager"
    assert me.json()["user"]["name"] == "Invited Person"

    members = await admin.get("/api/org/users", params={"q": invitee})
    member = members.json()["items"][0]
    assert member["status"] == "active"
    assert member["email_verified"] is True


async def test_google_links_existing_password_account(make_client, google_enabled, monkeypatch):
    owner: AsyncClient = make_client()
    reg = await register(owner)
    email = reg["user"]["email"]

    fake_google(monkeypatch, identity_for(email, name="Different Name"))
    other: AsyncClient = make_client()
    state = await start_flow(other)
    res = await other.get("/api/auth/google/callback", params={"code": "x", "state": state})
    assert "error" not in res.headers["location"]

    me = await other.get("/api/auth/me")
    assert me.json()["user"]["id"] == reg["user"]["id"]
    assert me.json()["user"]["name"] == reg["user"]["name"]


async def test_unverified_google_email_is_rejected(
    client: AsyncClient, google_enabled, monkeypatch
):
    fake_google(monkeypatch, identity_for(unique_email(), verified=False))
    state = await start_flow(client)
    res = await client.get("/api/auth/google/callback", params={"code": "x", "state": state})
    assert res.headers["location"] == f"{APP}/login?error=google_email_unverified"
    assert ACCESS_COOKIE not in client.cookies


async def test_suspended_user_cannot_google_login(make_client, google_enabled, monkeypatch):
    settings = get_settings()
    victim: AsyncClient = make_client()
    reg = await register(victim)

    sa: AsyncClient = make_client()
    await sa.post(
        "/api/auth/login",
        json={"email": str(settings.super_admin_email), "password": settings.super_admin_password},
    )
    assert (await sa.post(f"/api/admin/users/{reg['user']['id']}/suspend")).status_code == 200

    fake_google(monkeypatch, identity_for(reg["user"]["email"]))
    fresh: AsyncClient = make_client()
    state = await start_flow(fresh)
    res = await fresh.get("/api/auth/google/callback", params={"code": "x", "state": state})
    assert res.headers["location"] == f"{APP}/login?error=account_suspended"
