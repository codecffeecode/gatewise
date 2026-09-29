import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth.accounts import find_user_by_email, get_role_by_key
from backend.auth.password import hash_password
from backend.db.models import Invitation, MembershipStatus, Org, Role, User, UserRole
from backend.errors import ConflictError, NotFoundError, ValidationError
from backend.org.invitations import (
    IssuedInvitation,
    issue_invitation,
    pending_invitation,
    reissue_invitation,
    revoke_pending_invitations,
)
from backend.schemas.pagination import PageParams


@dataclass(frozen=True)
class MemberRow:
    membership: UserRole
    invitation: Invitation | None


def _member_query(org_id: uuid.UUID) -> Select:
    return (
        select(UserRole)
        .join(UserRole.user)
        .join(UserRole.role)
        .where(UserRole.org_id == org_id)
        .options(selectinload(UserRole.user), selectinload(UserRole.role))
    )


async def get_member(db: AsyncSession, *, org_id: uuid.UUID, user_id: uuid.UUID) -> UserRole:
    stmt = _member_query(org_id).where(UserRole.user_id == user_id)
    membership = (await db.execute(stmt)).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("User is not a member of this organization", code="member_not_found")
    return membership


async def list_members(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    params: PageParams,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[MemberRow], int]:
    stmt = _member_query(org_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    if role:
        stmt = stmt.where(Role.key == role)
    if status:
        stmt = stmt.where(UserRole.status == status)

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        (
            await db.execute(
                stmt.order_by(User.name, User.email).offset(params.offset).limit(params.page_size)
            )
        )
        .scalars()
        .all()
    )

    invited_emails = [m.user.email for m in rows if m.status == MembershipStatus.invited]
    invitations: dict[str, Invitation] = {}
    if invited_emails:
        inv_stmt = (
            select(Invitation)
            .where(
                Invitation.org_id == org_id,
                Invitation.email.in_(invited_emails),
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
            )
            .options(selectinload(Invitation.invited_by))
            .order_by(Invitation.created_at)
        )
        for inv in (await db.execute(inv_stmt)).scalars():
            invitations[inv.email] = inv

    return [MemberRow(m, invitations.get(m.user.email)) for m in rows], int(total or 0)


async def count_members(db: AsyncSession, org_id: uuid.UUID) -> tuple[int, int]:
    active = await db.scalar(
        select(func.count())
        .select_from(UserRole)
        .where(UserRole.org_id == org_id, UserRole.status != MembershipStatus.invited)
    )
    invited = await db.scalar(
        select(func.count())
        .select_from(UserRole)
        .where(UserRole.org_id == org_id, UserRole.status == MembershipStatus.invited)
    )
    return int(active or 0), int(invited or 0)


async def count_active_admins(db: AsyncSession, org_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(UserRole)
        .join(UserRole.role)
        .where(
            UserRole.org_id == org_id,
            UserRole.status == MembershipStatus.active,
            Role.key == "admin",
        )
    )
    return int(await db.scalar(stmt) or 0)


async def ensure_not_last_admin(db: AsyncSession, membership: UserRole) -> None:
    if membership.role.key != "admin" or membership.status != MembershipStatus.active:
        return
    if await count_active_admins(db, membership.org_id) <= 1:
        raise ConflictError(
            "An organization must keep at least one active admin", code="last_admin"
        )


async def _get_or_create_placeholder_user(db: AsyncSession, *, email: str, name: str) -> User:
    user = await find_user_by_email(db, email)
    if user is None:
        user = User(email=email, name=name, password_hash=None)
        db.add(user)
        await db.flush()
    return user


async def invite_member(
    db: AsyncSession,
    *,
    org: Org,
    email: str,
    role_key: str,
    invited_by: User | None,
) -> tuple[UserRole, IssuedInvitation]:
    role = await get_role_by_key(db, role_key)
    user = await _get_or_create_placeholder_user(
        db, email=email, name=email.split("@")[0].replace(".", " ").title()
    )

    existing = (
        await db.execute(_member_query(org.id).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()
    if existing is not None and existing.status != MembershipStatus.invited:
        raise ConflictError("User is already a member of this organization", code="already_member")
    if existing is not None:
        raise ConflictError(
            "User already has a pending invitation; resend it instead",
            code="already_invited",
        )

    membership = UserRole(
        user_id=user.id, org_id=org.id, role_id=role.id, status=MembershipStatus.invited
    )
    db.add(membership)
    await db.flush()
    issued = await issue_invitation(
        db,
        org_id=org.id,
        email=email,
        role_id=role.id,
        invited_by_user_id=invited_by.id if invited_by else None,
    )
    return await get_member(db, org_id=org.id, user_id=user.id), issued


async def resend_invitation(
    db: AsyncSession, *, org: Org, user_id: uuid.UUID, actor: User | None
) -> tuple[UserRole, IssuedInvitation]:
    membership = await get_member(db, org_id=org.id, user_id=user_id)
    if membership.status != MembershipStatus.invited:
        raise ConflictError("User has already accepted their invitation", code="not_invited")

    inv = await pending_invitation(db, org_id=org.id, email=membership.user.email)
    if inv is None:
        issued = await issue_invitation(
            db,
            org_id=org.id,
            email=membership.user.email,
            role_id=membership.role_id,
            invited_by_user_id=actor.id if actor else None,
        )
    else:
        issued = await reissue_invitation(db, inv)
    return membership, issued


async def create_member(
    db: AsyncSession,
    *,
    org: Org,
    email: str,
    name: str,
    password: str,
    role_key: str,
) -> UserRole:
    role = await get_role_by_key(db, role_key)
    user = await find_user_by_email(db, email)
    if user is None:
        user = User(email=email, name=name, password_hash=hash_password(password))
        db.add(user)
        await db.flush()
    elif user.password_hash is None:
        user.name = name
        user.password_hash = hash_password(password)

    existing = (
        await db.execute(_member_query(org.id).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()
    if existing is not None and existing.status != MembershipStatus.invited:
        raise ConflictError("User is already a member of this organization", code="already_member")

    if existing is not None:
        existing.status = MembershipStatus.active
        existing.role_id = role.id
        await revoke_pending_invitations(db, org_id=org.id, email=user.email)
    else:
        db.add(
            UserRole(
                user_id=user.id, org_id=org.id, role_id=role.id, status=MembershipStatus.active
            )
        )
    await db.flush()
    return await get_member(db, org_id=org.id, user_id=user.id)


async def update_member(
    db: AsyncSession,
    membership: UserRole,
    *,
    name: str | None,
    role_key: str | None,
) -> UserRole:
    if name is not None:
        membership.user.name = name.strip()
    if role_key is not None and role_key != membership.role.key:
        await ensure_not_last_admin(db, membership)
        membership.role = await get_role_by_key(db, role_key)
    await db.flush()
    return membership


async def set_member_status(
    db: AsyncSession, membership: UserRole, status: MembershipStatus
) -> UserRole:
    if membership.status == MembershipStatus.invited:
        raise ValidationError("User has not accepted their invitation yet", code="not_active")
    if membership.status == status:
        return membership
    if status == MembershipStatus.suspended:
        await ensure_not_last_admin(db, membership)
    membership.status = status
    await db.flush()
    return membership


async def remove_member(db: AsyncSession, membership: UserRole) -> None:
    await ensure_not_last_admin(db, membership)
    user = membership.user
    await revoke_pending_invitations(db, org_id=membership.org_id, email=user.email)
    await db.delete(membership)
    await db.flush()

    remaining = await db.scalar(
        select(func.count()).select_from(UserRole).where(UserRole.user_id == user.id)
    )
    if not remaining and user.password_hash is None and not user.is_super_admin:
        await db.delete(user)
        await db.flush()


async def list_roles_with_counts(db: AsyncSession, org_id: uuid.UUID) -> list[tuple[Role, int]]:
    counts = (
        select(UserRole.role_id, func.count().label("n"))
        .where(UserRole.org_id == org_id, UserRole.status != MembershipStatus.invited)
        .group_by(UserRole.role_id)
        .subquery()
    )
    stmt = (
        select(Role, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.role_id == Role.id)
        .options(selectinload(Role.permissions))
        .order_by(Role.created_at)
    )
    return [(role, int(n)) for role, n in (await db.execute(stmt)).all()]
