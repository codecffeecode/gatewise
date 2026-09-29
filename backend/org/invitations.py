import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth.tokens import generate_opaque_token, hash_token
from backend.config import get_settings
from backend.db.models import Invitation
from backend.mailer.templates import send_invitation_email

INVITATION_TTL = timedelta(days=7)


@dataclass
class IssuedInvitation:
    invitation: Invitation
    token: str
    email_sent: bool | None = None

    @property
    def accept_url(self) -> str:
        return f"{get_settings().app_url.rstrip('/')}/invite/{self.token}"


async def deliver_invitation(
    issued: IssuedInvitation, *, org_name: str, role_name: str, invited_by: str | None
) -> IssuedInvitation:
    if not get_settings().email_enabled:
        issued.email_sent = None
        return issued
    result = await send_invitation_email(
        to_email=issued.invitation.email,
        org_name=org_name,
        role_name=role_name,
        invited_by=invited_by,
        accept_url=issued.accept_url,
        expires_at=issued.invitation.expires_at,
    )
    issued.email_sent = result.delivered
    return issued


def invitation_status(inv: Invitation, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if inv.accepted_at is not None:
        return "accepted"
    if inv.revoked_at is not None:
        return "revoked"
    if inv.expires_at <= now:
        return "expired"
    return "pending"


async def pending_invitation(
    db: AsyncSession, *, org_id: uuid.UUID, email: str
) -> Invitation | None:
    stmt = (
        select(Invitation)
        .where(
            Invitation.org_id == org_id,
            Invitation.email == email.lower(),
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .order_by(Invitation.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def issue_invitation(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    email: str,
    role_id: uuid.UUID,
    invited_by_user_id: uuid.UUID | None,
) -> IssuedInvitation:
    existing = await pending_invitation(db, org_id=org_id, email=email)
    if existing is not None:
        existing.revoked_at = datetime.now(UTC)

    token = generate_opaque_token()
    inv = Invitation(
        org_id=org_id,
        email=email.lower(),
        role_id=role_id,
        invited_by_user_id=invited_by_user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + INVITATION_TTL,
    )
    db.add(inv)
    await db.flush()
    return IssuedInvitation(invitation=inv, token=token)


async def reissue_invitation(db: AsyncSession, inv: Invitation) -> IssuedInvitation:
    token = generate_opaque_token()
    inv.token_hash = hash_token(token)
    inv.expires_at = datetime.now(UTC) + INVITATION_TTL
    inv.sent_count += 1
    inv.revoked_at = None
    await db.flush()
    return IssuedInvitation(invitation=inv, token=token)


async def revoke_pending_invitations(db: AsyncSession, *, org_id: uuid.UUID, email: str) -> None:
    inv = await pending_invitation(db, org_id=org_id, email=email)
    if inv is not None:
        inv.revoked_at = datetime.now(UTC)
        await db.flush()


async def find_invitation_by_token(db: AsyncSession, token: str) -> Invitation | None:
    stmt = (
        select(Invitation)
        .where(Invitation.token_hash == hash_token(token))
        .options(
            selectinload(Invitation.org),
            selectinload(Invitation.role),
            selectinload(Invitation.invited_by),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()
