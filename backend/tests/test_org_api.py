from httpx import AsyncClient

from backend.config import get_settings
from backend.tests.test_auth_api import PASSWORD, register, unique_email


def token_from(url: str) -> str:
    return url.rsplit("/", 1)[-1]


async def test_full_member_lifecycle(make_client):
    admin: AsyncClient = make_client()
    me = await register(admin)
    admin_id = me["user"]["id"]

    org = await admin.get("/api/org")
    assert org.status_code == 200
    assert org.json()["member_count"] == 1

    renamed = await admin.patch("/api/org", json={"name": "Test Org Renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Test Org Renamed"

    invitee_email = unique_email()
    invited = await admin.post(
        "/api/org/users/invite", json={"email": invitee_email, "role": "employee"}
    )
    assert invited.status_code == 201, invited.text
    invitee = invited.json()
    assert invitee["status"] == "invited"
    first_url = invitee["invitation"]["accept_url"]
    assert first_url and "/invite/" in first_url

    dup = await admin.post("/api/org/users/invite", json={"email": invitee_email})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "already_invited"

    listing = await admin.get("/api/org/users", params={"page_size": 1})
    assert listing.status_code == 200
    page = listing.json()
    assert page["total"] == 2 and page["total_pages"] == 2 and len(page["items"]) == 1

    only_invited = await admin.get("/api/org/users", params={"status": "invited"})
    assert [u["email"] for u in only_invited.json()["items"]] == [invitee_email]

    resent = await admin.post(f"/api/org/users/{invitee['user_id']}/resend-invite")
    assert resent.status_code == 200
    second_url = resent.json()["invitation"]["accept_url"]
    assert second_url != first_url
    assert resent.json()["invitation"]["sent_count"] == 2

    stale = await admin.get(f"/api/invitations/{token_from(first_url)}")
    assert stale.status_code == 404

    public = await admin.get(f"/api/invitations/{token_from(second_url)}")
    assert public.status_code == 200
    assert public.json()["status"] == "pending"
    assert public.json()["requires_password"] is True

    employee: AsyncClient = make_client()
    accepted = await employee.post(
        f"/api/invitations/{token_from(second_url)}/accept",
        json={"name": "Eve Employee", "password": PASSWORD},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["org"]["role"] == "employee"
    employee_id = accepted.json()["user"]["id"]

    twice = await employee.post(
        f"/api/invitations/{token_from(second_url)}/accept", json={"password": PASSWORD}
    )
    assert twice.status_code == 422
    assert twice.json()["error"]["code"] == "invitation_accepted"

    denied = await employee.post("/api/org/users/invite", json={"email": unique_email()})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    promoted = await admin.patch(f"/api/org/users/{employee_id}", json={"role": "manager"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "manager"

    manager_can_invite = await employee.post(
        "/api/org/users/invite", json={"email": unique_email(), "role": "employee"}
    )
    assert manager_can_invite.status_code == 201
    pending_id = manager_can_invite.json()["user_id"]

    manager_admin_grant = await employee.post(
        "/api/org/users/invite", json={"email": unique_email(), "role": "admin"}
    )
    assert manager_admin_grant.status_code == 403
    assert manager_admin_grant.json()["error"]["code"] == "admin_role_restricted"

    self_role = await admin.patch(f"/api/org/users/{admin_id}", json={"role": "employee"})
    assert self_role.status_code == 403
    assert self_role.json()["error"]["code"] == "self_modification"

    self_suspend = await admin.post(f"/api/org/users/{admin_id}/suspend")
    assert self_suspend.status_code == 403

    suspend_pending = await admin.post(f"/api/org/users/{pending_id}/suspend")
    assert suspend_pending.status_code == 422
    assert suspend_pending.json()["error"]["code"] == "not_active"

    suspended = await admin.post(f"/api/org/users/{employee_id}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    locked_out = await employee.get("/api/org/users")
    assert locked_out.status_code == 403
    assert locked_out.json()["error"]["code"] == "org_required"

    reactivated = await admin.post(f"/api/org/users/{employee_id}/reactivate")
    assert reactivated.status_code == 200
    assert (await employee.get("/api/org/users")).status_code == 200

    sessions = await admin.get(f"/api/org/users/{employee_id}/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1

    revoked = await admin.delete(f"/api/org/users/{employee_id}/sessions")
    assert revoked.status_code == 204
    kicked = await employee.get("/api/auth/me")
    assert kicked.status_code == 401
    assert kicked.json()["error"]["code"] == "session_revoked"

    created = await admin.post(
        "/api/org/users",
        json={
            "email": unique_email(),
            "name": "Direct Dan",
            "password": PASSWORD,
            "role": "employee",
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "active"
    dan: AsyncClient = make_client()
    dan_login = await dan.post(
        "/api/auth/login", json={"email": created.json()["email"], "password": PASSWORD}
    )
    assert dan_login.status_code == 200

    roles = await admin.get("/api/org/roles")
    assert roles.status_code == 200
    by_key = {r["key"]: r for r in roles.json()["roles"]}
    assert by_key["admin"]["member_count"] == 1
    assert by_key["manager"]["member_count"] == 1
    assert by_key["employee"]["member_count"] == 1
    assert len(roles.json()["permissions"]) == 12

    removed = await admin.delete(f"/api/org/users/{pending_id}")
    assert removed.status_code == 204
    gone = await admin.get(f"/api/org/users/{pending_id}")
    assert gone.status_code == 404

    audit = await admin.get("/api/org/audit", params={"page_size": 50})
    assert audit.status_code == 200
    actions = {a["action"] for a in audit.json()["items"]}
    assert {
        "auth.register",
        "org.update",
        "users.invite",
        "users.resend_invite",
        "users.accept_invite",
        "users.update",
        "users.suspend",
        "users.reactivate",
        "sessions.revoke_all",
        "users.create",
        "users.delete",
    } <= actions

    filtered = await admin.get("/api/org/audit", params={"action": "users."})
    assert all(a["action"].startswith("users.") for a in filtered.json()["items"])


async def test_last_admin_is_protected(make_client):
    admin: AsyncClient = make_client()
    me = await register(admin)
    admin_id, org_id = me["user"]["id"], me["org"]["id"]

    settings = get_settings()
    sa: AsyncClient = make_client()
    await sa.post(
        "/api/auth/login",
        json={"email": str(settings.super_admin_email), "password": settings.super_admin_password},
    )
    assert (await sa.post("/api/auth/switch-org", json={"org_id": org_id})).status_code == 200

    for attempt in (
        sa.patch(f"/api/org/users/{admin_id}", json={"role": "employee"}),
        sa.post(f"/api/org/users/{admin_id}/suspend"),
        sa.delete(f"/api/org/users/{admin_id}"),
    ):
        res = await attempt
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == "last_admin"

    second = await sa.post(
        "/api/org/users",
        json={"email": unique_email(), "name": "Second", "password": PASSWORD, "role": "admin"},
    )
    assert second.status_code == 201

    demoted = await sa.patch(f"/api/org/users/{admin_id}", json={"role": "employee"})
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "employee"

    downgraded = await admin.get("/api/auth/me")
    assert downgraded.json()["org"]["role"] == "employee"


async def test_own_sessions_list_and_revoke(make_client):
    a: AsyncClient = make_client()
    me = await register(a)
    b: AsyncClient = make_client()
    await b.post("/api/auth/login", json={"email": me["user"]["email"], "password": PASSWORD})

    sessions = await a.get("/api/auth/sessions")
    assert sessions.status_code == 200
    rows = sessions.json()
    assert len(rows) == 2
    assert sum(1 for s in rows if s["current"]) == 1
    other = next(s for s in rows if not s["current"])

    revoked = await a.delete(f"/api/auth/sessions/{other['id']}")
    assert revoked.status_code == 204
    assert (await b.get("/api/auth/me")).status_code == 401
    assert (await a.get("/api/auth/me")).status_code == 200


async def test_super_admin_endpoints(make_client):
    settings = get_settings()
    sa: AsyncClient = make_client()
    login = await sa.post(
        "/api/auth/login",
        json={"email": str(settings.super_admin_email), "password": settings.super_admin_password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["is_super_admin"] is True

    stats = await sa.get("/api/admin/stats")
    assert stats.status_code == 200
    assert stats.json()["orgs"] >= 1

    admin_email = unique_email()
    created = await sa.post(
        "/api/admin/orgs",
        json={"name": "Test Org Platform", "admin_email": admin_email},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["slug"].startswith("test-org-platform")
    assert body["pending_invites"] == 1
    assert body["admin_invitation"]["accept_url"]

    orgs = await sa.get("/api/admin/orgs", params={"q": body["slug"]})
    assert orgs.json()["total"] == 1

    users = await sa.get("/api/admin/users", params={"q": admin_email})
    assert users.json()["total"] == 1
    assert users.json()["items"][0]["has_password"] is False

    switched = await sa.post("/api/auth/switch-org", json={"org_id": body["id"]})
    assert switched.status_code == 200
    assert len(switched.json()["org"]["permissions"]) == 12
    inside = await sa.get("/api/org/users")
    assert inside.status_code == 200
    assert inside.json()["total"] == 1

    disabled = await sa.patch(f"/api/admin/orgs/{body['id']}", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    regular: AsyncClient = make_client()
    reg = await register(regular)
    forbidden = await regular.get("/api/admin/stats")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "super_admin_required"

    suspended = await sa.post(f"/api/admin/users/{reg['user']['id']}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    blocked = await regular.get("/api/auth/me")
    assert blocked.status_code == 401
    relogin = await regular.post(
        "/api/auth/login", json={"email": reg["user"]["email"], "password": PASSWORD}
    )
    assert relogin.status_code == 401
    assert relogin.json()["error"]["code"] == "account_suspended"

    self_suspend = await sa.post(f"/api/admin/users/{login.json()['user']['id']}/suspend")
    assert self_suspend.status_code == 403

    deleted = await sa.delete(f"/api/admin/users/{reg['user']['id']}")
    assert deleted.status_code == 204
