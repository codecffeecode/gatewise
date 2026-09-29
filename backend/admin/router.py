import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from backend.audit import record_audit
from backend.auth.accounts import unique_org_slug
from backend.auth.deps import Client, CurrentPrincipal, Principal
from backend.auth.sessions import revoke_all_user_sessions
from backend.db.models import Invitation, MembershipStatus, Org, Session, User, UserRole, UserStatus
from backend.db.session import DbSession
from backend.errors import ConflictError, NotFoundError, PermissionDeniedError
from backend.org import members as svc
from backend.org.invitations import deliver_invitation
from backend.org.presenters import present_invitation
from backend.schemas.admin import (
    CreateOrgRequest,
    GlobalMembership,
    GlobalUserOut,
    OrgCreated,
    PlatformStats,
    UpdateOrgRequest,
)
from backend.schemas.org import OrgDetail
from backend.schemas.pagination import Page, Paging

router = APIRouter(prefix="/admin", tags=["super admin"])


async def get_super_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.user.is_super_admin:
        raise PermissionDeniedError("Super admin access required", code="super_admin_required")
    return principal


SuperAdmin = Annotated[Principal, Depends(get_super_admin)]


async def _org_detail(db, org: Org) -> OrgDetail:
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


@router.get("/stats", response_model=PlatformStats)
async def stats(_: SuperAdmin, db: DbSession) -> PlatformStats:
    orgs = await db.scalar(select(func.count()).select_from(Org))
    users = await db.scalar(select(func.count()).select_from(User))
    sessions = await db.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.revoked_at.is_(None), Session.expires_at > func.now())
    )
    invites = await db.scalar(
        select(func.count())
        .select_from(UserRole)
        .where(UserRole.status == MembershipStatus.invited)
    )
    return PlatformStats(
        orgs=orgs or 0,
        users=users or 0,
        active_sessions=sessions or 0,
        pending_invites=invites or 0,
    )


@router.get("/orgs", response_model=Page[OrgDetail])
async def list_orgs(
    _: SuperAdmin,
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[OrgDetail]:
    stmt = select(Org)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Org.name.ilike(pattern), Org.slug.ilike(pattern)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    orgs = (
        (await db.execute(stmt.order_by(Org.name).offset(paging.offset).limit(paging.page_size)))
        .scalars()
        .all()
    )
    return Page.build(
        [await _org_detail(db, org) for org in orgs], params=paging, total=int(total or 0)
    )


@router.post("/orgs", response_model=OrgCreated, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: CreateOrgRequest, principal: SuperAdmin, db: DbSession, client: Client
) -> OrgCreated:
    if body.slug:
        taken = await db.scalar(select(Org.id).where(Org.slug == body.slug))
        if taken is not None:
            raise ConflictError("Slug is already in use", code="slug_taken")
        slug = body.slug
    else:
        slug = await unique_org_slug(db, body.name)

    org = Org(name=body.name.strip(), slug=slug)
    db.add(org)
    await db.flush()

    issued = None
    if body.admin_email:
        membership, issued = await svc.invite_member(
            db, org=org, email=body.admin_email, role_key="admin", invited_by=principal.user
        )
        await deliver_invitation(
            issued,
            org_name=org.name,
            role_name=membership.role.name,
            invited_by=principal.user.name,
        )

    await record_audit(
        db,
        action="admin.org.create",
        actor_user_id=principal.user.id,
        org_id=org.id,
        target_type="org",
        target_id=org.id,
        metadata={"slug": slug, "admin_email": body.admin_email},
        ip_address=client.ip_address,
    )
    await db.commit()

    detail = await _org_detail(db, org)
    return OrgCreated(
        **detail.model_dump(),
        admin_invitation=present_invitation(issued.invitation, issued) if issued else None,
    )


@router.patch("/orgs/{org_id}", response_model=OrgDetail)
async def update_org(
    org_id: uuid.UUID,
    body: UpdateOrgRequest,
    principal: SuperAdmin,
    db: DbSession,
    client: Client,
) -> OrgDetail:
    org = await db.get(Org, org_id)
    if org is None:
        raise NotFoundError("Organization not found", code="org_not_found")

    changes: dict = {}
    if body.name is not None and body.name.strip() != org.name:
        changes["name"] = {"from": org.name, "to": body.name.strip()}
        org.name = body.name.strip()
    if body.enabled is not None and body.enabled != org.enabled:
        changes["enabled"] = {"from": org.enabled, "to": body.enabled}
        org.enabled = body.enabled

    if changes:
        await record_audit(
            db,
            action="admin.org.update",
            actor_user_id=principal.user.id,
            org_id=org.id,
            target_type="org",
            target_id=org.id,
            metadata=changes,
            ip_address=client.ip_address,
        )
    await db.commit()
    return await _org_detail(db, org)


def _present_user(user: User) -> GlobalUserOut:
    return GlobalUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_super_admin=user.is_super_admin,
        email_verified=user.email_verified_at is not None,
        has_password=user.password_hash is not None,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        memberships=[
            GlobalMembership(
                org_id=m.org.id,
                org_name=m.org.name,
                org_slug=m.org.slug,
                role=m.role.key,
                status=m.status,
            )
            for m in sorted(user.memberships, key=lambda m: m.org.name)
        ],
    )


@router.get("/users", response_model=Page[GlobalUserOut])
async def list_users(
    _: SuperAdmin,
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[GlobalUserOut]:
    stmt = select(User)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    users = (
        (
            await db.execute(
                stmt.options(
                    selectinload(User.memberships).selectinload(UserRole.org),
                    selectinload(User.memberships).selectinload(UserRole.role),
                )
                .order_by(User.created_at.desc())
                .offset(paging.offset)
                .limit(paging.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page.build([_present_user(u) for u in users], params=paging, total=int(total or 0))


async def _load_user(db, user_id: uuid.UUID) -> User:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.memberships).selectinload(UserRole.org),
            selectinload(User.memberships).selectinload(UserRole.role),
        )
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    return user


async def _set_user_status(
    user_id: uuid.UUID, new_status: UserStatus, principal: Principal, db, client: Client
) -> GlobalUserOut:
    if user_id == principal.user.id:
        raise PermissionDeniedError("You cannot change your own status", code="self_modification")
    user = await _load_user(db, user_id)
    if user.is_super_admin:
        raise PermissionDeniedError(
            "Super admins cannot be suspended", code="super_admin_protected"
        )
    if user.status != new_status:
        user.status = new_status
        revoked = 0
        suspending = new_status == UserStatus.suspended
        if suspending:
            revoked = await revoke_all_user_sessions(db, user.id, reason="account_suspended")
        await record_audit(
            db,
            action="admin.user.suspend" if suspending else "admin.user.reactivate",
            actor_user_id=principal.user.id,
            target_type="user",
            target_id=user.id,
            metadata={"email": user.email, "revoked_sessions": revoked},
            ip_address=client.ip_address,
        )
    await db.commit()
    return _present_user(user)


@router.post("/users/{user_id}/suspend", response_model=GlobalUserOut)
async def suspend_user(
    user_id: uuid.UUID, principal: SuperAdmin, db: DbSession, client: Client
) -> GlobalUserOut:
    return await _set_user_status(user_id, UserStatus.suspended, principal, db, client)


@router.post("/users/{user_id}/reactivate", response_model=GlobalUserOut)
async def reactivate_user(
    user_id: uuid.UUID, principal: SuperAdmin, db: DbSession, client: Client
) -> GlobalUserOut:
    return await _set_user_status(user_id, UserStatus.active, principal, db, client)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, principal: SuperAdmin, db: DbSession, client: Client
) -> Response:
    if user_id == principal.user.id:
        raise PermissionDeniedError("You cannot delete your own account", code="self_modification")
    user = await _load_user(db, user_id)
    if user.is_super_admin:
        raise PermissionDeniedError("Super admins cannot be deleted", code="super_admin_protected")

    email = user.email
    await db.execute(
        Invitation.__table__.update()
        .where(Invitation.email == email, Invitation.accepted_at.is_(None))
        .values(revoked_at=func.now())
    )
    await db.delete(user)
    await record_audit(
        db,
        action="admin.user.delete",
        actor_user_id=principal.user.id,
        target_type="user",
        target_id=user_id,
        metadata={"email": email},
        ip_address=client.ip_address,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
