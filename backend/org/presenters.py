import uuid

from backend.config import get_settings
from backend.db.models import AuditLog, Invitation, Role, Session, User, UserRole
from backend.org.invitations import IssuedInvitation
from backend.schemas.org import AuditOut, InvitationSummary, MemberOut, RoleOut, SessionOut


def invite_links_visible() -> bool:
    return not get_settings().brevo_api_key


def present_invitation(
    inv: Invitation | None, issued: IssuedInvitation | None = None
) -> InvitationSummary | None:
    if inv is None:
        return None
    return InvitationSummary(
        id=inv.id,
        expires_at=inv.expires_at,
        sent_count=inv.sent_count,
        invited_by=inv.invited_by.name if inv.invited_by else None,
        created_at=inv.created_at,
        accept_url=(
            issued.accept_url
            if issued and (invite_links_visible() or issued.email_sent is False)
            else None
        ),
        email_sent=issued.email_sent if issued else None,
    )


def present_member(
    membership: UserRole,
    invitation: Invitation | None = None,
    issued: IssuedInvitation | None = None,
) -> MemberOut:
    user = membership.user
    return MemberOut(
        user_id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        role=membership.role.key,
        role_name=membership.role.name,
        status=membership.status,
        is_super_admin=user.is_super_admin,
        email_verified=user.email_verified_at is not None,
        last_login_at=user.last_login_at,
        joined_at=membership.created_at,
        invitation=present_invitation(invitation, issued),
    )


def present_role(role: Role, member_count: int) -> RoleOut:
    return RoleOut(
        id=role.id,
        key=role.key,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(p.key for p in role.permissions),
        member_count=member_count,
    )


def present_session(session: Session, *, current_session_id: uuid.UUID | None) -> SessionOut:
    return SessionOut(
        id=session.id,
        user_id=session.user_id,
        active_org_id=session.active_org_id,
        user_agent=session.user_agent,
        ip_address=str(session.ip_address) if session.ip_address else None,
        created_at=session.created_at,
        last_used_at=session.last_used_at,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
        revoked_reason=session.revoked_reason,
        current=session.id == current_session_id,
    )


def present_audit(entry: AuditLog, actor: User | None) -> AuditOut:
    return AuditOut(
        id=entry.id,
        action=entry.action,
        actor_user_id=entry.actor_user_id,
        actor_email=actor.email if actor else None,
        actor_name=actor.name if actor else None,
        target_type=entry.target_type,
        target_id=entry.target_id,
        metadata=entry.metadata_,
        ip_address=str(entry.ip_address) if entry.ip_address else None,
        created_at=entry.created_at,
    )
