from datetime import UTC, datetime

from fastapi import APIRouter, Response

from backend.audit import record_audit
from backend.auth.accounts import find_user_by_email, mark_email_verified
from backend.auth.cookies import set_auth_cookies
from backend.auth.deps import Client
from backend.auth.password import hash_password
from backend.auth.presenters import present_auth
from backend.auth.service import start_session
from backend.db.models import MembershipStatus, UserRole
from backend.db.session import DbSession
from backend.errors import NotFoundError, ValidationError
from backend.org.invitations import find_invitation_by_token, invitation_status
from backend.org.members import get_member
from backend.schemas.auth import AuthResponse
from backend.schemas.org import AcceptInvitationRequest, InvitationPublic

router = APIRouter(prefix="/invitations", tags=["invitations"])


async def _load(db, token: str):
    inv = await find_invitation_by_token(db, token)
    if inv is None:
        raise NotFoundError("Invitation not found", code="invitation_not_found")
    return inv


@router.get("/{token}", response_model=InvitationPublic)
async def get_invitation(token: str, db: DbSession) -> InvitationPublic:
    inv = await _load(db, token)
    user = await find_user_by_email(db, inv.email)
    return InvitationPublic(
        email=inv.email,
        org_name=inv.org.name,
        role=inv.role.key,
        role_name=inv.role.name,
        invited_by=inv.invited_by.name if inv.invited_by else None,
        expires_at=inv.expires_at,
        requires_password=user is None or user.password_hash is None,
        status=invitation_status(inv),
    )


@router.post("/{token}/accept", response_model=AuthResponse)
async def accept_invitation(
    token: str,
    body: AcceptInvitationRequest,
    response: Response,
    db: DbSession,
    client: Client,
) -> AuthResponse:
    inv = await _load(db, token)
    state = invitation_status(inv)
    if state != "pending":
        raise ValidationError(f"Invitation is {state}", code=f"invitation_{state}")

    invited_user = await find_user_by_email(db, inv.email)
    if invited_user is None:
        raise NotFoundError("Invited user no longer exists", code="invitation_orphaned")
    membership: UserRole = await get_member(db, org_id=inv.org_id, user_id=invited_user.id)
    user = membership.user

    if user.password_hash is None:
        if not body.password:
            raise ValidationError(
                "Choose a password to finish setting up", code="password_required"
            )
        user.password_hash = hash_password(body.password)
    if body.name:
        user.name = body.name.strip()
    mark_email_verified(user)

    membership.status = MembershipStatus.active
    membership.role_id = inv.role_id
    inv.accepted_at = datetime.now(UTC)
    await db.flush()

    result = await start_session(
        db, user, user_agent=client.user_agent, ip_address=client.ip_address, org_id=inv.org_id
    )
    await record_audit(
        db,
        action="users.accept_invite",
        actor_user_id=user.id,
        org_id=inv.org_id,
        target_type="user",
        target_id=user.id,
        ip_address=client.ip_address,
    )
    await db.commit()

    set_auth_cookies(response, access_token=result.access_token, refresh_token=result.refresh_token)
    return await present_auth(
        db,
        user=result.user,
        session=result.session,
        org_context=result.org_context,
        access_token=result.access_token,
        access_expires_at=result.access_expires_at,
    )
