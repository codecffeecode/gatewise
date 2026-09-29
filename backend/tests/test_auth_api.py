import uuid

from httpx import AsyncClient

from backend.auth.cookies import ACCESS_COOKIE, REFRESH_COOKIE

PASSWORD = "Test@12345"


def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@gatewise.test"


async def register(client: AsyncClient, **overrides) -> dict:
    payload = {
        "email": unique_email(),
        "password": PASSWORD,
        "name": "Test Person",
        "org_name": f"Test Org {uuid.uuid4().hex[:6]}",
    }
    payload.update(overrides)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


async def test_register_sets_cookies_and_creates_admin_org(client: AsyncClient):
    body = await register(client)

    assert body["user"]["email"].startswith("test-")
    assert body["org"]["role"] == "admin"
    assert "users:invite" in body["org"]["permissions"]
    assert body["orgs"][0]["role"] == "admin"
    assert body["access_token"]
    assert ACCESS_COOKIE in client.cookies
    assert REFRESH_COOKIE in client.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["id"] == body["user"]["id"]


async def test_register_duplicate_email_conflicts(client: AsyncClient):
    body = await register(client)
    res = await client.post(
        "/api/auth/register",
        json={"email": body["user"]["email"].upper(), "password": PASSWORD, "name": "Dup"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


async def test_login_wrong_password_and_success(client: AsyncClient):
    body = await register(client)
    email = body["user"]["email"]
    client.cookies.clear()

    bad = await client.post("/api/auth/login", json={"email": email, "password": "Wrong@12345"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"
    assert ACCESS_COOKIE not in client.cookies

    unknown = await client.post(
        "/api/auth/login", json={"email": unique_email(), "password": PASSWORD}
    )
    assert unknown.status_code == 401

    good = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert good.status_code == 200
    assert good.json()["org"]["id"] == body["org"]["id"]
    assert ACCESS_COOKIE in client.cookies


async def test_me_requires_auth(client: AsyncClient):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


async def test_bearer_header_works_without_cookies(client: AsyncClient):
    body = await register(client)
    client.cookies.clear()

    res = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert res.status_code == 200


async def test_refresh_rotates_and_old_token_is_rejected(client: AsyncClient):
    await register(client)
    first_refresh = client.cookies[REFRESH_COOKIE]

    res = await client.post("/api/auth/refresh")
    assert res.status_code == 200, res.text
    second_refresh = client.cookies[REFRESH_COOKIE]
    assert second_refresh != first_refresh

    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/auth")
    reused = await client.post("/api/auth/refresh")
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_invalid"

    client.cookies.set(REFRESH_COOKIE, second_refresh, path="/api/auth")
    revoked = await client.post("/api/auth/refresh")
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "session_revoked"


async def test_logout_revokes_session(client: AsyncClient):
    body = await register(client)
    token = body["access_token"]

    res = await client.post("/api/auth/logout")
    assert res.status_code == 204
    assert ACCESS_COOKIE not in client.cookies

    after = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "session_revoked"


async def test_switch_org_denied_for_non_member(client: AsyncClient):
    other = await register(client)
    client.cookies.clear()
    await register(client)

    res = await client.post("/api/auth/switch-org", json={"org_id": other["org"]["id"]})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "org_access_denied"


async def test_switch_org_to_own_org_succeeds(client: AsyncClient):
    body = await register(client)
    res = await client.post("/api/auth/switch-org", json={"org_id": body["org"]["id"]})
    assert res.status_code == 200
    assert res.json()["org"]["id"] == body["org"]["id"]


async def test_validation_errors(client: AsyncClient):
    res = await client.post(
        "/api/auth/register", json={"email": "nope", "password": "short", "name": ""}
    )
    assert res.status_code == 422
