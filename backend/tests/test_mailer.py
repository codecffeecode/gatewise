import json
from datetime import UTC, datetime

import httpx
import pytest
from httpx import AsyncClient

from backend.config import get_settings
from backend.mailer import brevo
from backend.mailer.templates import send_invitation_email
from backend.tests.test_auth_api import register, unique_email


@pytest.fixture
def brevo_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-test")
    monkeypatch.setattr(settings, "email_from", "Gatewise Demo <demo@example.test>")
    return settings


@pytest.fixture
def brevo_capture():
    calls: list[dict] = []
    status = {"code": 201}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "api_key": request.headers.get("api-key"),
                "body": json.loads(request.content),
            }
        )
        if status["code"] >= 400:
            return httpx.Response(status["code"], json={"message": "boom"})
        return httpx.Response(201, json={"messageId": "<msg-123>"})

    brevo.use_transport(httpx.MockTransport(handler))
    yield calls, status
    brevo.use_transport(None)


async def test_send_skipped_when_not_configured():
    result = await send_invitation_email(
        to_email="x@gatewise.test",
        org_name="Acme",
        role_name="Employee",
        invited_by="Alice",
        accept_url="http://localhost:3000/invite/abc",
        expires_at=datetime.now(UTC),
    )
    assert result.delivered is False
    assert result.reason == "not_configured"


async def test_send_posts_to_brevo(brevo_configured, brevo_capture):
    calls, _ = brevo_capture
    result = await send_invitation_email(
        to_email="x@gatewise.test",
        org_name="Acme Corp",
        role_name="Manager",
        invited_by="Alice Johnson",
        accept_url="http://localhost:3000/invite/abc",
        expires_at=datetime.now(UTC),
    )
    assert result.delivered is True
    assert result.message_id == "<msg-123>"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == brevo.BREVO_ENDPOINT
    assert call["api_key"] == "xkeysib-test"
    body = call["body"]
    assert body["sender"] == {"name": "Gatewise Demo", "email": "demo@example.test"}
    assert body["to"] == [{"email": "x@gatewise.test"}]
    assert "Acme Corp" in body["subject"]
    assert "http://localhost:3000/invite/abc" in body["htmlContent"]
    assert "Alice Johnson has invited you" in body["textContent"]


async def test_invite_endpoint_sends_email_and_hides_link(
    client: AsyncClient, brevo_configured, brevo_capture
):
    calls, status = brevo_capture
    await register(client)

    invited = await client.post("/api/org/users/invite", json={"email": unique_email()})
    assert invited.status_code == 201, invited.text
    inv = invited.json()["invitation"]
    assert inv["email_sent"] is True
    assert inv["accept_url"] is None
    assert len(calls) == 1

    status["code"] = 500
    failed = await client.post("/api/org/users/invite", json={"email": unique_email()})
    assert failed.status_code == 201
    inv = failed.json()["invitation"]
    assert inv["email_sent"] is False
    assert inv["accept_url"]
