import logging
from dataclasses import dataclass

import httpx

from backend.config import get_settings

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
log = logging.getLogger("gatewise.mailer")


@dataclass(frozen=True)
class EmailResult:
    delivered: bool
    reason: str | None = None
    message_id: str | None = None


_transport: httpx.AsyncBaseTransport | None = None


def use_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


async def send_email(
    *, to_email: str, to_name: str | None, subject: str, html: str, text: str
) -> EmailResult:
    settings = get_settings()
    if not settings.email_enabled:
        log.info("email not configured; skipping '%s' to %s", subject, to_email)
        return EmailResult(delivered=False, reason="not_configured")

    sender_name, sender_email = settings.email_sender
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }
    headers = {"api-key": settings.brevo_api_key, "accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0, transport=_transport) as client:
            res = await client.post(BREVO_ENDPOINT, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("brevo request failed: %s", exc)
        return EmailResult(delivered=False, reason="network_error")

    if res.status_code >= 400:
        log.warning("brevo rejected email (%s): %s", res.status_code, res.text[:300])
        return EmailResult(delivered=False, reason=f"http_{res.status_code}")

    message_id = None
    try:
        message_id = res.json().get("messageId")
    except ValueError:
        pass
    return EmailResult(delivered=True, message_id=message_id)
