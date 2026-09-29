from datetime import datetime
from html import escape

from backend.mailer.brevo import EmailResult, send_email


def _layout(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:32px 16px;background:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#18181b">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center">
<table role="presentation" width="520" cellspacing="0" cellpadding="0" style="max-width:520px;background:#fff;border-radius:12px;border:1px solid #e4e4e7">
<tr><td style="padding:28px 32px 8px;font-size:18px;font-weight:600">Gatewise</td></tr>
<tr><td style="padding:0 32px 24px;font-size:22px;font-weight:700">{escape(title)}</td></tr>
<tr><td style="padding:0 32px 32px;font-size:15px;line-height:1.55">{body_html}</td></tr>
</table>
<p style="font-size:12px;color:#71717a;margin-top:16px">You received this because someone entered your address in Gatewise. If this wasn't expected, you can ignore this email.</p>
</td></tr></table></body></html>"""


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
        'style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;'
        'padding:12px 20px;border-radius:8px;font-weight:600">'
        f"{escape(label)}</a></p>"
    )


async def send_invitation_email(
    *,
    to_email: str,
    org_name: str,
    role_name: str,
    invited_by: str | None,
    accept_url: str,
    expires_at: datetime,
) -> EmailResult:
    who = f"{invited_by} has invited you" if invited_by else "You have been invited"
    expiry = expires_at.strftime("%d %b %Y")
    subject = f"You're invited to join {org_name} on Gatewise"
    html = _layout(
        f"Join {org_name}",
        f"<p>{escape(who)} to join <strong>{escape(org_name)}</strong> as "
        f"<strong>{escape(role_name)}</strong>.</p>"
        + _button(accept_url, "Accept invitation")
        + f'<p style="color:#71717a;font-size:13px">This link expires on {expiry}. '
        f"If the button doesn't work, paste this into your browser:<br>"
        f'<span style="word-break:break-all">{escape(accept_url)}</span></p>',
    )
    text = (
        f"{who} to join {org_name} as {role_name}.\n\n"
        f"Accept the invitation: {accept_url}\n\nThis link expires on {expiry}."
    )
    return await send_email(to_email=to_email, to_name=None, subject=subject, html=html, text=text)
