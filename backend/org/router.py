import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.audit import record_audit
from backend.auth.deps import Client, Principal, require_permission
from backend.auth.permissions import PERMISSIONS
from backend.auth.sessions import revoke_session
from backend.db.models import AuditLog, MembershipStatus, Session, User
from backend.db.session import DbSession
from backend.errors import NotFoundError, PermissionDeniedError
from backend.org import members as svc
from backend.org.invitations import deliver_invitation
from backend.org.presenters import (
    present_audit,
    present_member,
    present_role,
    present_session,
)
from backend.schemas.org import (
    AuditOut,
    CreateMemberRequest,
    InviteRequest,
    MemberOut,
    MemberStatus,
    OrgDetail,
    OrgUpdate,
    PermissionOut,
    RolesResponse,
    SessionOut,
    UpdateMemberRequest,
)
from backend.schemas.pagination import Page, Paging

router = APIRouter(prefix="/org", tags=["organization"])


def perm(*keys: str):
    return Annotated[Principal, Depends(require_permission(*keys))]


def _ensure_org(principal: Principal) -> Principal:
    if principal.org is None:
        raise PermissionDeniedError("Select an organization first", code="org_required")
    return principal


def _ensure_not_self(principal: Principal, user_id: uuid.UUID) -> None:
    if principal.user.id == user_id:
        raise PermissionDeniedError(
            "You cannot perform this action on your own account", code="self_modification"
        )


def _ensure_can_assign_role(principal: Principal, *roles: str | None) -> None:
    if "admin" in roles and not principal.has("roles:update"):
        raise PermissionDeniedError(
            "Only admins can grant or remove the admin role", code="admin_role_restricted"
        )


async def _present_org(db, principal: Principal) -> OrgDetail:
    org = principal.org.org
    member_count, pending = await svc.count_members(db, org.id)
    return OrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        enabled=org.enabled,
        created_at=org.created_at,
        member_count=member_count,
        pending_invites=pending,
    )


@router.get("", response_model=OrgDetail)
async def get_org(principal: perm("org:read"), db: DbSession) -> OrgDetail:
    _ensure_org(principal)
    return await _present_org(db, principal)


@router.patch("", response_model=OrgDetail)
async def update_org(
    body: OrgUpdate, principal: perm("org:update"), db: DbSession, client: Client
) -> OrgDetail:
    _ensure_org(principal)
    org = principal.org.org
    previous = org.name
    org.name = body.name.strip()
    await record_audit(
        db,
        action="org.update",
        actor_user_id=principal.user.id,
        org_id=org.id,
        target_type="org",
        target_id=org.id,
        metadata={"from": previous, "to": org.name},
        ip_address=client.ip_address,
    )
    await db.commit()
    return await _present_org(db, principal)


@router.get("/users", response_model=Page[MemberOut])
async def list_users(
    principal: perm("users:read"),
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query()] = None,
    member_status: Annotated[MemberStatus | None, Query(alias="status")] = None,
) -> Page[MemberOut]:
    _ensure_org(principal)
    rows, total = await svc.list_members(
        db, org_id=principal.org_id, params=paging, q=q, role=role, status=member_status
    )
    return Page.build(
        [present_member(r.membership, r.invitation) for r in rows], params=paging, total=total
    )


@router.post("/users/invite", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteRequest, principal: perm("users:invite"), db: DbSession, client: Client
) -> MemberOut:
    _ensure_org(principal)
    _ensure_can_assign_role(principal, body.role)
    membership, issued = await svc.invite_member(
        db, org=principal.org.org, email=body.email, role_key=body.role, invited_by=principal.user
    )
    await deliver_invitation(
        issued,
        org_name=principal.org.org.name,
        role_name=membership.role.name,
        invited_by=principal.user.name,
    )
    await record_audit(
        db,
        action="users.invite",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=membership.user_id,
        metadata={"email": body.email, "role": body.role, "email_sent": issued.email_sent},
        ip_address=client.ip_address,
    )
    await db.commit()
    return present_member(membership, issued.invitation, issued)


@router.post("/users/{user_id}/resend-invite", response_model=MemberOut)
async def resend_invite(
    user_id: uuid.UUID, principal: perm("users:invite"), db: DbSession, client: Client
) -> MemberOut:
    _ensure_org(principal)
    membership, issued = await svc.resend_invitation(
        db, org=principal.org.org, user_id=user_id, actor=principal.user
    )
    await deliver_invitation(
        issued,
        org_name=principal.org.org.name,
        role_name=membership.role.name,
        invited_by=principal.user.name,
    )
    await record_audit(
        db,
        action="users.resend_invite",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=user_id,
        metadata={"sent_count": issued.invitation.sent_count, "email_sent": issued.email_sent},
        ip_address=client.ip_address,
    )
    await db.commit()
    return present_member(membership, issued.invitation, issued)


@router.post("/users", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateMemberRequest, principal: perm("users:invite"), db: DbSession, client: Client
) -> MemberOut:
    _ensure_org(principal)
    _ensure_can_assign_role(principal, body.role)
    membership = await svc.create_member(
        db,
        org=principal.org.org,
        email=body.email,
        name=body.name,
        password=body.password,
        role_key=body.role,
    )
    await record_audit(
        db,
        action="users.create",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=membership.user_id,
        metadata={"email": body.email, "role": body.role},
        ip_address=client.ip_address,
    )
    await db.commit()
    return present_member(membership)


@router.get("/users/{user_id}", response_model=MemberOut)
async def get_user(user_id: uuid.UUID, principal: perm("users:read"), db: DbSession) -> MemberOut:
    _ensure_org(principal)
    membership = await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    return present_member(membership)


@router.patch("/users/{user_id}", response_model=MemberOut)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateMemberRequest,
    principal: perm("users:update"),
    db: DbSession,
    client: Client,
) -> MemberOut:
    _ensure_org(principal)
    membership = await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    changes: dict = {}
    if body.role is not None and body.role != membership.role.key:
        _ensure_not_self(principal, user_id)
        _ensure_can_assign_role(principal, body.role, membership.role.key)
        changes["role"] = {"from": membership.role.key, "to": body.role}
    if body.name is not None and body.name.strip() != membership.user.name:
        changes["name"] = {"from": membership.user.name, "to": body.name.strip()}

    membership = await svc.update_member(db, membership, name=body.name, role_key=body.role)
    if changes:
        await record_audit(
            db,
            action="users.update",
            actor_user_id=principal.user.id,
            org_id=principal.org_id,
            target_type="user",
            target_id=user_id,
            metadata=changes,
            ip_address=client.ip_address,
        )
    await db.commit()
    return present_member(membership)


async def _set_status(
    user_id: uuid.UUID,
    new_status: MembershipStatus,
    principal: Principal,
    db,
    client: Client,
    action: str,
) -> MemberOut:
    _ensure_org(principal)
    _ensure_not_self(principal, user_id)
    membership = await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    membership = await svc.set_member_status(db, membership, new_status)
    await record_audit(
        db,
        action=action,
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=user_id,
        ip_address=client.ip_address,
    )
    await db.commit()
    return present_member(membership)


@router.post("/users/{user_id}/suspend", response_model=MemberOut)
async def suspend_user(
    user_id: uuid.UUID, principal: perm("users:suspend"), db: DbSession, client: Client
) -> MemberOut:
    return await _set_status(
        user_id, MembershipStatus.suspended, principal, db, client, "users.suspend"
    )


@router.post("/users/{user_id}/reactivate", response_model=MemberOut)
async def reactivate_user(
    user_id: uuid.UUID, principal: perm("users:suspend"), db: DbSession, client: Client
) -> MemberOut:
    return await _set_status(
        user_id, MembershipStatus.active, principal, db, client, "users.reactivate"
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, principal: perm("users:delete"), db: DbSession, client: Client
) -> Response:
    _ensure_org(principal)
    _ensure_not_self(principal, user_id)
    membership = await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    email = membership.user.email
    await svc.remove_member(db, membership)
    await record_audit(
        db,
        action="users.delete",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=user_id,
        metadata={"email": email},
        ip_address=client.ip_address,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/roles", response_model=RolesResponse)
async def list_roles(principal: perm("roles:read"), db: DbSession) -> RolesResponse:
    _ensure_org(principal)
    roles = await svc.list_roles_with_counts(db, principal.org_id)
    return RolesResponse(
        roles=[present_role(role, n) for role, n in roles],
        permissions=[PermissionOut(key=k, description=d) for k, d in PERMISSIONS.items()],
    )


def _org_sessions_query(org_id: uuid.UUID, user_id: uuid.UUID):
    return select(Session).where(Session.user_id == user_id, Session.active_org_id == org_id)


@router.get("/users/{user_id}/sessions", response_model=list[SessionOut])
async def list_user_sessions(
    user_id: uuid.UUID, principal: perm("sessions:read"), db: DbSession
) -> list[SessionOut]:
    _ensure_org(principal)
    await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    stmt = (
        _org_sessions_query(principal.org_id, user_id)
        .where(Session.revoked_at.is_(None), Session.expires_at > func.now())
        .order_by(Session.last_used_at.desc())
    )
    sessions = (await db.execute(stmt)).scalars().all()
    return [present_session(s, current_session_id=principal.session.id) for s in sessions]


@router.delete("/users/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_session(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    principal: perm("sessions:revoke"),
    db: DbSession,
    client: Client,
) -> Response:
    _ensure_org(principal)
    stmt = _org_sessions_query(principal.org_id, user_id).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError("Session not found", code="session_not_found")
    await revoke_session(db, session, reason="revoked_by_admin")
    await record_audit(
        db,
        action="sessions.revoke",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="session",
        target_id=session_id,
        metadata={"user_id": str(user_id)},
        ip_address=client.ip_address,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_user_sessions(
    user_id: uuid.UUID, principal: perm("sessions:revoke"), db: DbSession, client: Client
) -> Response:
    _ensure_org(principal)
    await svc.get_member(db, org_id=principal.org_id, user_id=user_id)
    stmt = _org_sessions_query(principal.org_id, user_id).where(Session.revoked_at.is_(None))
    sessions = (await db.execute(stmt)).scalars().all()
    for session in sessions:
        await revoke_session(db, session, reason="revoked_by_admin")
    await record_audit(
        db,
        action="sessions.revoke_all",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="user",
        target_id=user_id,
        metadata={"revoked_sessions": len(sessions)},
        ip_address=client.ip_address,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audit", response_model=Page[AuditOut])
async def list_audit(
    principal: perm("audit:read"),
    db: DbSession,
    paging: Paging,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[AuditOut]:
    _ensure_org(principal)
    actor = aliased(User)
    stmt = (
        select(AuditLog, actor)
        .outerjoin(actor, actor.id == AuditLog.actor_user_id)
        .where(AuditLog.org_id == principal.org_id)
    )
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.execute(
            stmt.order_by(AuditLog.created_at.desc()).offset(paging.offset).limit(paging.page_size)
        )
    ).all()
    return Page.build(
        [present_audit(entry, who) for entry, who in rows], params=paging, total=int(total or 0)
    )
