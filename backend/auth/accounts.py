import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.password import hash_password, needs_rehash, verify_password
from backend.db.models import MembershipStatus, Org, Role, User, UserRole
from backend.errors import AuthenticationError, ConflictError

_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


@dataclass(frozen=True)
class Registration:
    user: User
    org: Org
    membership: UserRole


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:48].strip("-") or "org"


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.strip().lower())
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_role_by_key(db: AsyncSession, key: str) -> Role:
    role = (await db.execute(select(Role).where(Role.key == key))).scalar_one_or_none()
    if role is None:
        raise RuntimeError(f"Role '{key}' is missing; run the seed first")
    return role


async def unique_org_slug(db: AsyncSession, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    while True:
        exists = await db.scalar(select(Org.id).where(Org.slug == candidate))
        if exists is None:
            return candidate
        candidate = f"{slug}-{secrets.token_hex(2)}"


async def register_with_new_org(
    db: AsyncSession, *, email: str, password: str, name: str, org_name: str | None
) -> Registration:
    if await find_user_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists", code="email_taken")

    org_label = (org_name or f"{name.split()[0]}'s Workspace").strip()
    org = Org(name=org_label, slug=await unique_org_slug(db, org_label))
    user = User(email=email, name=name.strip(), password_hash=hash_password(password))
    db.add_all([org, user])
    await db.flush()

    admin_role = await get_role_by_key(db, "admin")
    membership = UserRole(
        user_id=user.id, org_id=org.id, role_id=admin_role.id, status=MembershipStatus.active
    )
    db.add(membership)
    await db.flush()
    return Registration(user=user, org=org, membership=membership)


async def authenticate_with_password(db: AsyncSession, *, email: str, password: str) -> User:
    user = await find_user_by_email(db, email)
    stored_hash = user.password_hash if user and user.password_hash else _DUMMY_HASH
    ok = verify_password(stored_hash, password)
    if user is None or user.password_hash is None or not ok:
        raise AuthenticationError("Incorrect email or password", code="invalid_credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await db.flush()
    return user


def mark_email_verified(user: User) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
