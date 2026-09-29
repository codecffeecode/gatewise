import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import MembershipStatus, Org, Role, User, UserRole


@dataclass(frozen=True)
class OrgContext:
    org: Org
    membership: UserRole | None
    role: Role | None
    permissions: frozenset[str]

    @property
    def role_key(self) -> str | None:
        return self.role.key if self.role else None


async def load_membership(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> UserRole | None:
    stmt = (
        select(UserRole)
        .where(UserRole.user_id == user_id, UserRole.org_id == org_id)
        .options(
            selectinload(UserRole.org),
            selectinload(UserRole.role).selectinload(Role.permissions),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_memberships(db: AsyncSession, user_id: uuid.UUID) -> list[UserRole]:
    stmt = (
        select(UserRole)
        .join(UserRole.org)
        .where(UserRole.user_id == user_id)
        .options(selectinload(UserRole.org), selectinload(UserRole.role))
        .order_by(Org.name)
    )
    return list((await db.execute(stmt)).scalars().all())


async def resolve_org_context(
    db: AsyncSession, user: User, org_id: uuid.UUID | None
) -> OrgContext | None:
    if org_id is None:
        return None

    membership = await load_membership(db, user.id, org_id)
    if membership is not None:
        if membership.status != MembershipStatus.active or not membership.org.enabled:
            return None
        perms = frozenset(p.key for p in membership.role.permissions)
        return OrgContext(
            org=membership.org, membership=membership, role=membership.role, permissions=perms
        )

    if user.is_super_admin:
        org = await db.get(Org, org_id)
        if org is None:
            return None
        return OrgContext(org=org, membership=None, role=None, permissions=frozenset())

    return None


async def pick_default_org_id(db: AsyncSession, user: User) -> uuid.UUID | None:
    stmt = (
        select(UserRole.org_id)
        .join(UserRole.org)
        .where(
            UserRole.user_id == user.id,
            UserRole.status == MembershipStatus.active,
            Org.enabled.is_(True),
        )
        .order_by(UserRole.created_at)
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
