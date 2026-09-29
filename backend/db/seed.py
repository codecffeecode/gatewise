import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.password import hash_password
from backend.auth.permissions import PERMISSIONS, ROLES, RoleKey
from backend.config import get_settings
from backend.db.models import (
    MembershipStatus,
    Org,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from backend.db.session import get_sessionmaker

DEMO_PASSWORD = "Demo@12345"


@dataclass(frozen=True)
class Membership:
    org: str
    role: RoleKey
    status: MembershipStatus = MembershipStatus.active


@dataclass(frozen=True)
class DemoUser:
    email: str
    name: str
    memberships: list[Membership] = field(default_factory=list)


DEMO_ORGS = [
    ("acme", "Acme Corp"),
    ("globex", "Globex Industries"),
]

DEMO_USERS = [
    DemoUser("alice@acme.test", "Alice Johnson", [Membership("acme", "admin")]),
    DemoUser("bob@acme.test", "Bob Martinez", [Membership("acme", "manager")]),
    DemoUser("carol@acme.test", "Carol Singh", [Membership("acme", "employee")]),
    DemoUser(
        "dave@acme.test",
        "Dave Kim",
        [Membership("acme", "employee", MembershipStatus.suspended)],
    ),
    DemoUser("erin@globex.test", "Erin Walsh", [Membership("globex", "admin")]),
    DemoUser("frank@globex.test", "Frank Osei", [Membership("globex", "employee")]),
    DemoUser(
        "grace@contractor.test",
        "Grace Liu",
        [Membership("acme", "manager"), Membership("globex", "employee")],
    ),
]

TABLES_IN_DELETE_ORDER = (
    "audit_logs",
    "invitations",
    "sessions",
    "user_roles",
    "role_permissions",
    "oauth_accounts",
    "permissions",
    "roles",
    "orgs",
    "users",
)


async def truncate_all(db: AsyncSession) -> None:
    tables = ", ".join(TABLES_IN_DELETE_ORDER)
    await db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    rows = [Permission(key=key, description=desc) for key, desc in PERMISSIONS.items()]
    db.add_all(rows)
    await db.flush()
    return {p.key: p for p in rows}


async def seed_roles(db: AsyncSession, perms: dict[str, Permission]) -> dict[RoleKey, Role]:
    roles: dict[RoleKey, Role] = {}
    for key, definition in ROLES.items():
        role = Role(
            key=key, name=definition.name, description=definition.description, is_system=True
        )
        db.add(role)
        roles[key] = role
    await db.flush()
    db.add_all(
        RolePermission(role_id=roles[key].id, permission_id=perms[perm].id)
        for key, definition in ROLES.items()
        for perm in definition.permissions
    )
    await db.flush()
    return roles


async def seed_orgs(db: AsyncSession) -> dict[str, Org]:
    orgs = {slug: Org(slug=slug, name=name) for slug, name in DEMO_ORGS}
    db.add_all(orgs.values())
    await db.flush()
    return orgs


async def seed_users(db: AsyncSession, orgs: dict[str, Org], roles: dict[RoleKey, Role]) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    demo_hash = hash_password(DEMO_PASSWORD)

    db.add(
        User(
            email=str(settings.super_admin_email),
            name="Gatewise Super Admin",
            password_hash=hash_password(settings.super_admin_password),
            is_super_admin=True,
            email_verified_at=now,
        )
    )

    users = {
        u.email: User(email=u.email, name=u.name, password_hash=demo_hash, email_verified_at=now)
        for u in DEMO_USERS
    }
    db.add_all(users.values())
    await db.flush()

    db.add_all(
        UserRole(
            user_id=users[u.email].id,
            org_id=orgs[m.org].id,
            role_id=roles[m.role].id,
            status=m.status,
        )
        for u in DEMO_USERS
        for m in u.memberships
    )
    await db.flush()


async def seed() -> None:
    async with get_sessionmaker()() as db:
        async with db.begin():
            await truncate_all(db)
            perms = await seed_permissions(db)
            roles = await seed_roles(db, perms)
            orgs = await seed_orgs(db)
            await seed_users(db, orgs, roles)


def main() -> None:
    asyncio.run(seed())
    settings = get_settings()
    print("Seed complete.")
    print(f"Super admin:   {settings.super_admin_email} / {settings.super_admin_password}")
    print(f"Demo users:    {', '.join(u.email for u in DEMO_USERS)}")
    print(f"Demo password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
